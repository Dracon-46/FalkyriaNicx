"""Assistentes: frases, armazenamento, prompt e ferramentas, rotas e o chat."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nicx.acoes import handle, parse
from nicx.acoes.intencoes import Action
from nicx.assistentes import armazenamento, pedidos, prontos, servico, sessao
from nicx.assistentes.modelo import Assistente, AssistenteInvalido


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    token = sessao.ATUAL.set(None)
    yield tmp_path / "home"
    sessao.ATUAL.reset(token)


def _tutor(**campos) -> Assistente:
    dados = {
        "nome": "Tutor de estudos",
        "instrucoes": "Explique passo a passo e faça uma pergunta no fim.",
        "saudacao": "Qual matéria hoje?",
    }
    dados.update(campos)
    return Assistente.de_dict(dados)


# ----------------------------------------------------------------- frases
@pytest.mark.parametrize(
    ("frase", "op", "alvo"),
    [
        ("fala com o assistente Tutor de estudos", "usar", "Tutor de estudos"),
        ("usa o assistente revisor, por favor", "usar", "revisor"),
        ("chama o assistente de estudos", "usar", "estudos"),
        ("volta pro Nicx", "sair", ""),
        ("volta para o nicx", "sair", ""),
        ("sai do assistente", "sair", ""),
        ("quais assistentes eu tenho?", "listar", ""),
        ("lista meus assistentes", "listar", ""),
        ("qual assistente está ativo?", "qual", ""),
        ("talk to the study tutor assistant", "usar", "study tutor"),
        ("use the reviewer assistant", "usar", "reviewer"),
        ("back to Nicx", "sair", ""),
        ("list my assistants", "listar", ""),
        ("habla con el asistente revisor", "usar", "revisor"),
        ("vuelve a Nicx", "sair", ""),
        ("parle à l'assistant tuteur", "usar", "tuteur"),
        ("reviens à Nicx", "sair", ""),
    ],
)
def test_frases(frase, op, alvo):
    assert parse(frase) == Action("assistente", op, target=alvo)


@pytest.mark.parametrize(
    ("frase", "kind"),
    [
        ("abre o chrome", "open"),
        ("aumenta o volume", "volume"),
        ("clica em Salvar", "ui"),
        ("me lembra de falar com o João daqui 5 minutos", "remind"),
    ],
)
def test_outras_acoes_continuam(frase, kind):
    assert parse(frase).kind == kind


def test_pelo_nome_so_se_existir():
    assert parse("fala com o Professor") is None
    armazenamento.criar(_tutor(nome="Professor"))
    assert parse("fala com o professor") == Action(
        "assistente", "usar", target="Professor"
    )


@pytest.mark.parametrize(
    ("frase", "descricao"),
    [
        (
            "cria um assistente que revisa contratos de aluguel",
            "que revisa contratos de aluguel",
        ),
        (
            "Nicx, monta um assistente para me ajudar com Receitas",
            "para me ajudar com Receitas",
        ),
        (
            "create an assistant that helps me learn Spanish",
            "that helps me learn Spanish",
        ),
        ("crea un asistente para estudiar historia", "para estudiar historia"),
        ("cria um assistente novo", None),
        ("cria um lembrete para amanhã", None),
    ],
)
def test_pedido_de_criacao(frase, descricao):
    assert pedidos.criacao(frase) == descricao


# ------------------------------------------------------------ armazenamento
def test_criar_listar_e_nome_repetido():
    criado = armazenamento.criar(_tutor())
    assert [a.nome for a in armazenamento.listar()] == ["Tutor de estudos"]
    assert armazenamento.obter(criado.id).instrucoes.startswith("Explique")
    with pytest.raises(AssistenteInvalido):
        armazenamento.criar(_tutor(nome="tutor de ESTUDOS"))


def test_por_nome_aceita_uma_palavra_se_so_um_combinar():
    armazenamento.criar(_tutor())
    armazenamento.criar(_tutor(nome="Tutor de inglês"))
    armazenamento.criar(_tutor(nome="Revisor de textos"))
    assert armazenamento.por_nome("revisor").nome == "Revisor de textos"
    assert armazenamento.por_nome("tutor") is None  # dois combinam
    assert armazenamento.por_nome("tutor de ingles").nome == "Tutor de inglês"


@pytest.mark.parametrize(
    "campos",
    [{"nome": ""}, {"instrucoes": ""}, {"nome": "x" * 41}, {"instrucoes": "x" * 2001}],
)
def test_validacao(campos):
    with pytest.raises(AssistenteInvalido):
        armazenamento.criar(_tutor(**campos))


def test_apagar_o_ativo_volta_para_o_nicx():
    a = armazenamento.criar(_tutor())
    armazenamento.definir_ativo(a.id)
    assert armazenamento.ativo().id == a.id
    assert armazenamento.apagar(a.id)
    assert armazenamento.ativo() is None and armazenamento.id_ativo() == ""


def test_atualizar_mantem_id():
    a = armazenamento.criar(_tutor())
    novo = armazenamento.atualizar(a.id, _tutor(nome="Tutor", instrucoes="Seja breve."))
    assert novo.id == a.id and armazenamento.obter(a.id).nome == "Tutor"
    with pytest.raises(KeyError):
        armazenamento.atualizar("nao-existe", _tutor())


def test_arquivo_corrompido(home):
    (home / "assistentes.json").write_text("{quebrado", encoding="utf-8")
    assert armazenamento.listar() == []
    assert (home / "assistentes.json.corrompido").exists()


def test_historico_e_desfazer():
    from nicx.historico import desfazer
    from nicx.historico.registro import registro

    armazenamento.criar(_tutor())
    linhas = [a.para_dict() for a in registro().listar()]
    assert (
        linhas[0]["tipo"] == "assistente" and "Tutor de estudos" in linhas[0]["titulo"]
    )
    assert desfazer.desfazer()[0]
    assert armazenamento.listar() == []


def test_prontos_em_varios_idiomas():
    pt = {a.modelo: a for a in prontos.prontos("pt-BR")}
    en = {a.modelo: a for a in prontos.prontos("en")}
    assert set(pt) == set(prontos.IDS) == set(en)
    assert (
        pt["estudos"].nome == "Tutor de estudos" and en["estudos"].nome == "Study tutor"
    )
    assert en["revisor"].instrucoes.startswith("Review") and not pt["revisor"].memoria
    assert pt["pesquisa"].ferramentas == ["web_search"]


def test_textos_com_as_mesmas_chaves():
    from nicx.assistentes import textos

    chaves = textos.chaves()
    assert all(c == chaves["pt-BR"] for c in chaves.values())


# ---------------------------------------------------------------- ações
def test_usar_qual_e_sair():
    armazenamento.criar(_tutor())
    saida = handle("fala com o assistente tutor de estudos")
    assert saida.ok and '"Tutor de estudos"' in saida.message
    assert "Qual matéria hoje?" in saida.message  # a saudação dele
    assert "já está ativo" in handle("fala com o assistente tutor de estudos").message
    assert "Tutor de estudos" in handle("qual assistente está ativo?").message
    assert "Nicx de sempre" in handle("volta pro Nicx").message
    assert armazenamento.ativo() is None
    assert "Nenhum assistente" in handle("qual assistente está ativo?").message


def test_nao_achou_sugere_e_lista():
    assert "ainda não tem" in handle("quais assistentes eu tenho?").message
    armazenamento.criar(_tutor())
    saida = handle("fala com o assistente cozinheiro")
    assert not saida.ok and "Você tem: Tutor de estudos" in saida.message
    assert (
        "Seus assistentes: Tutor de estudos" in handle("lista meus assistentes").message
    )


# ------------------------------------------------------- prompt e ferramentas
def test_secao_no_prompt():
    from nicx.cerebro.prompt.builder import SystemPromptBuilder

    builder = SystemPromptBuilder(agent_template="Você é o Nicx.")
    assert "Assistente" not in builder.build()
    sessao.ATUAL.set(_tutor())
    prompt = builder.build()
    assert prompt.startswith("Você é o Nicx.")  # o começo continua igual
    assert '"Tutor de estudos"' in prompt and "pergunta no fim" in prompt


class _Ferramenta:
    def __init__(self, nome):
        from nicx.ferramentas._stubs import ToolSpec

        self.spec = ToolSpec(name=nome, description=f"faz {nome}")
        self.chamadas = 0

    def execute(self, **_k):
        from nicx.ferramentas._stubs import ToolResult

        self.chamadas += 1
        return ToolResult(tool_name=self.spec.name, content="feito", success=True)

    def to_openai_function(self):
        return {"type": "function", "function": {"name": self.spec.name}}


def test_executor_so_usa_as_ferramentas_do_assistente():
    from nicx.ferramentas._stubs import ToolExecutor
    from nicx.nucleo.types import ToolCall

    busca, shell = _Ferramenta("web_search"), _Ferramenta("shell_exec")
    executor = ToolExecutor([busca, shell], autonomia=False)
    assert len(executor.get_openai_tools()) == 2
    sessao.ATUAL.set(_tutor(ferramentas=["web_search"]))
    nomes = [t["function"]["name"] for t in executor.get_openai_tools()]
    assert nomes == ["web_search"]
    recusa = executor.execute(ToolCall(id="1", name="shell_exec", arguments="{}"))
    assert not recusa.success and "não usa a ferramenta shell_exec" in recusa.content
    assert shell.chamadas == 0
    sessao.ATUAL.set(_tutor(ferramentas=["*"]))
    assert len(executor.get_openai_tools()) == 2


# ------------------------------------------------------------ montar (modelo)
def test_ler_proposta_tolera_texto_e_filtra_ferramentas():
    resposta = (
        "<think>hmm</think>Claro!\n```json\n"
        + json.dumps(
            {
                "nome": "Revisor de contratos",
                "descricao": "Lê contratos e aponta riscos.",
                "instrucoes": "Leia o contrato e liste as cláusulas de risco.",
                "ferramentas": ["file_read", "ferramenta_inventada"],
                "saudacao": "Mande o contrato.",
            },
            ensure_ascii=False,
        )
        + "\n```"
    )
    a = servico.ler_proposta(resposta, {"file_read": "lê arquivos"})
    assert a.nome == "Revisor de contratos" and a.ferramentas == ["file_read"]
    with pytest.raises(AssistenteInvalido):
        servico.ler_proposta("não sei", {})


def test_montar_salva_com_nome_livre():
    armazenamento.criar(_tutor(nome="Revisor"))
    engine = MagicMock()
    engine.generate.return_value = {
        "content": json.dumps(
            {"nome": "Revisor", "instrucoes": "Revise.", "descricao": "Revisa."}
        )
    }
    frase = servico.montar("que revisa textos", "pt-BR", engine, "m", {})
    assert '"Revisor 2"' in frase and armazenamento.por_nome("Revisor 2") is not None
    pedido = engine.generate.call_args.args[0][0].content
    assert "que revisa textos" in pedido


# ---------------------------------------------------------------------- rotas
def _client(resposta="Resposta do modelo."):
    from fastapi.testclient import TestClient

    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.app import create_app

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.context_from_memory = False
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.is_cloud = False
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": resposta,
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    memory = MagicMock()
    memory.list_facts.return_value = []
    app = create_app(engine, "m", config=cfg, memory_service=memory)
    return TestClient(app), engine, memory


def test_rotas_crud_e_ativo():
    client, _, _ = _client()
    dados = client.get("/v1/assistentes", params={"idioma": "en"}).json()
    assert dados["assistentes"] == [] and dados["ativo"] is None
    assert {p["modelo"] for p in dados["prontos"]} == set(prontos.IDS)
    assert dados["limites"]["instrucoes"] == 2000
    corpo = {"nome": "Tutor", "instrucoes": "Explique.", "ferramentas": []}
    criado = client.post("/v1/assistentes", json=corpo).json()
    assert client.post("/v1/assistentes", json=corpo).status_code == 400
    assert client.put("/v1/assistentes/ativo", json={"id": criado["id"]}).json() == {
        "ativo": criado["id"]
    }
    assert client.get("/v1/assistentes").json()["ativo"] == criado["id"]
    assert client.put("/v1/assistentes/ativo", json={"id": "x"}).status_code == 404
    corpo["nome"] = "Tutor 2"
    alterado = client.put(f"/v1/assistentes/{criado['id']}", json=corpo).json()
    assert alterado["nome"] == "Tutor 2" and alterado["id"] == criado["id"]
    assert client.delete(f"/v1/assistentes/{criado['id']}").json() == {"ok": True}
    assert client.get("/v1/assistentes").json()["ativo"] is None
    assert client.delete(f"/v1/assistentes/{criado['id']}").status_code == 404


def test_rota_propor_nao_salva():
    proposta = {
        "nome": "Chef",
        "instrucoes": "Sugira receitas.",
        "descricao": "Receitas.",
    }
    client, _, _ = _client(json.dumps(proposta))
    dados = client.post(
        "/v1/assistentes/propor", json={"descricao": "receitas veganas"}
    )
    assert dados.status_code == 200 and dados.json()["nome"] == "Chef"
    assert "id" not in dados.json() and armazenamento.listar() == []


def _pedir(client, frase):
    corpo = {"model": "m", "messages": [{"role": "user", "content": frase}]}
    return client.post("/v1/chat/completions", json=corpo).json()["choices"][0][
        "message"
    ]["content"]


def test_chat_usa_as_instrucoes_do_assistente_ativo():
    a = armazenamento.criar(_tutor(memoria=False))
    armazenamento.definir_ativo(a.id)
    client, engine, memory = _client()
    assert _pedir(client, "me explica fotossíntese") == "Resposta do modelo."
    sistema = engine.generate.call_args.args[0][0]
    assert sistema.role.value == "system" and "pergunta no fim" in sistema.content
    memory.submit.assert_not_called()  # este assistente fica fora da memória
    armazenamento.definir_ativo(None)
    _pedir(client, "me explica fotossíntese")
    assert "pergunta no fim" not in engine.generate.call_args.args[0][0].content
    memory.submit.assert_called_once()


def test_chat_cria_assistente_pela_frase():
    proposta = {
        "nome": "Chef vegano",
        "instrucoes": "Sugira receitas.",
        "descricao": "Receitas.",
    }
    client, _, _ = _client(json.dumps(proposta, ensure_ascii=False))
    resposta = _pedir(client, "cria um assistente que sugere receitas veganas")
    assert '"Chef vegano"' in resposta and armazenamento.por_nome("chef vegano")


def test_assistente_sem_ferramentas_vai_direto():
    from nicx.servidor.rotas.chat import _assistant_has_tools

    agente = MagicMock()
    agente._tools = [_Ferramenta("web_search")]
    assert _assistant_has_tools(None, agente)
    assert not _assistant_has_tools(_tutor(), agente)
    assert _assistant_has_tools(_tutor(ferramentas=["web_search"]), agente)


def test_pasta_dos_testes():
    assert Path(__file__).parent.name == "assistentes"
