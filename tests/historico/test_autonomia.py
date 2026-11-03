"""Autonomia: regra, portão das ferramentas, ações do modelo, frases e textos."""

from __future__ import annotations

import pytest

from nicx.acoes import confirmacao, executores, notas, parse
from nicx.acoes.intencoes import Action
from nicx.acoes.sistema import run
from nicx.ferramentas._stubs import BaseTool, ToolExecutor, ToolSpec
from nicx.historico import autonomia, textos
from nicx.historico.registro import registro
from nicx.nucleo.types import ToolCall, ToolResult


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"
    confirmacao.drop()


@pytest.fixture
def nivel(monkeypatch):
    def _usar(n: str) -> None:
        monkeypatch.setattr(autonomia, "nivel_atual", lambda: n)

    return _usar


@pytest.mark.parametrize(
    ("risco", "observador", "assistido", "autonomo"),
    [
        ("leitura", False, False, False),
        ("leve", True, False, False),
        ("moderado", True, True, False),
        ("alto", True, True, True),
    ],
)
def test_regra_por_nivel(risco, observador, assistido, autonomo):
    assert autonomia.precisa_confirmar(risco, "observador") is observador
    assert autonomia.precisa_confirmar(risco, "assistido") is assistido
    assert autonomia.precisa_confirmar(risco, "autonomo") is autonomo


def test_riscos_das_ferramentas():
    assert autonomia.risco_ferramenta("file_read") == "leitura"
    assert autonomia.risco_ferramenta("file_write") == "moderado"
    assert autonomia.risco_ferramenta("shell_exec") == "alto"
    assert autonomia.risco_ferramenta("qualquer", pede_confirmacao=True) == "alto"
    assert autonomia.risco_ferramenta("http_request", {"method": "get"}) == "leitura"
    assert autonomia.risco_ferramenta("http_request", {"method": "POST"}) == "moderado"
    assert autonomia.risco_acao("power", "abort") == "leitura"
    assert autonomia.risco_acao("power", "shutdown") == "alto"


class _Escreve(BaseTool):
    tool_id = "file_write"

    def __init__(self, destino):
        self.destino = destino

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name="file_write", description="escreve")

    def execute(self, **params) -> ToolResult:
        self.destino.write_text(params.get("content", ""), encoding="utf-8")
        return ToolResult(tool_name="file_write", content="gravado", success=True)


def _chamar(executor, destino, conteudo="oi"):
    import json

    return executor.execute(
        ToolCall(
            id="1",
            name="file_write",
            arguments=json.dumps({"path": str(destino), "content": conteudo}),
        )
    )


def test_assistido_espera_confirmo_para_escrever(tmp_path, nivel):
    nivel("assistido")
    destino = tmp_path / "a.txt"
    res = _chamar(ToolExecutor([_Escreve(destino)]), destino)
    assert not res.success and res.metadata.get("aguardando_confirmacao")
    assert "confirmo" in res.content and not destino.exists()
    saida = executores.confirm()
    assert saida.ok and "Feito (file_write)" in saida.message
    assert destino.read_text(encoding="utf-8") == "oi"
    resultados = [a.resultado for a in registro().listar(tipos=["ferramenta"])]
    assert resultados == ["ok", "pendente"]


def test_autonomo_escreve_direto_e_deixa_desfazer(tmp_path, nivel):
    nivel("autonomo")
    destino = tmp_path / "b.txt"
    res = _chamar(ToolExecutor([_Escreve(destino)]), destino)
    assert res.success and destino.exists()
    from nicx.historico.desfazer import desfazer

    assert desfazer()[0] and not destino.exists()


def test_quem_confirma_na_hora_decide(tmp_path, nivel):
    nivel("observador")
    destino = tmp_path / "c.txt"
    sim = ToolExecutor(
        [_Escreve(destino)], interactive=True, confirm_callback=lambda _p: True
    )
    assert _chamar(sim, destino).success
    nao = ToolExecutor(
        [_Escreve(destino)], interactive=True, confirm_callback=lambda _p: False
    )
    assert not _chamar(nao, destino, "x").success
    assert destino.read_text(encoding="utf-8") == "oi"


def test_operacao_direta_ignora_o_nivel(tmp_path, nivel):
    nivel("observador")
    destino = tmp_path / "d.txt"
    assert _chamar(ToolExecutor([_Escreve(destino)], autonomia=False), destino).success


def test_comando_do_usuario_nao_pede_confirmacao(nivel):
    nivel("observador")
    assert run(Action("note_add", target="comprar pão")).ok
    assert notas.all_notes() == ["comprar pão"]


def test_pedido_do_modelo_respeita_o_nivel(nivel):
    nivel("observador")
    pedido = run(Action("note_add", target="ligar"), pelo_modelo=True)
    assert "confirmo" in pedido.message and notas.all_notes() == []
    assert executores.confirm().ok
    assert notas.all_notes() == ["ligar"]


@pytest.mark.parametrize(
    ("frase", "idioma", "kind"),
    [
        ("desfaz", None, "undo"),
        ("desfaz isso", None, "undo"),
        ("o que você fez?", None, "historico"),
        ("undo that", "en", "undo"),
        ("what did you do today", "en", "historico"),
        ("deshaz eso", "es", "undo"),
        ("défais ça", "fr", "undo"),
        ("撤销", "zh", "undo"),
        ("पूर्ववत करो", "hi", "undo"),
        ("تراجع", "ar", "undo"),
    ],
)
def test_frases(frase, idioma, kind):
    acao = parse(frase, idioma)
    assert acao is not None and acao.kind == kind


def test_desfazer_a_organizacao_continua_igual():
    acao = parse("desfaz a organização")
    assert acao is not None and acao.kind == "organize_undo"


def test_o_que_voce_fez(nivel):
    nivel("assistido")
    assert executores.historico().message == "Ainda não fiz nada que valha anotar."
    notas.add("comprar pão")
    assert executores.historico().message.startswith(
        "O que fiz por último: Anotação: comprar pão"
    )


def test_textos_com_as_mesmas_chaves():
    chaves = textos.chaves()
    referencia = chaves["pt-BR"]
    for codigo, conjunto in chaves.items():
        assert conjunto == referencia, codigo
