"""Modo Trabalho: pasta presa, ferramentas, desfazer e o fluxo com o modelo."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from nicx.trabalho import executor, ferramentas, modelo, servico
from nicx.trabalho.modelo import Passo, Tarefa
from nicx.trabalho.pasta import ForaDaPasta, Pasta, validar_pasta


@pytest.fixture
def pasta(tmp_path) -> Path:
    p = tmp_path / "trabalho"
    p.mkdir()
    (p / "notas.txt").write_bytes("compra 10,50\nvenda 30".encode())
    (p / "sub").mkdir()
    (p / "sub" / "a.md").write_text("# A", encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _sem_tarefa_solta():
    """Nenhuma tarefa de um teste continua rodando no seguinte."""
    yield
    r = servico._em_curso()
    if r:
        servico.parar(r.tarefa.id)
    with servico._LOCK:
        servico._ATUAL = None


def _ferramentas(
    pasta: Path, confirmar=lambda _t: True
) -> tuple[Tarefa, ferramentas.Ferramentas]:
    tarefa = Tarefa(id=modelo.novo_id(), pasta=str(pasta), pedido="teste")
    return tarefa, ferramentas.Ferramentas(
        tarefa, confirmar, lambda: modelo.salvar(tarefa)
    )


# ------------------------------------------------------------------- pasta


def test_caminho_fora_da_pasta_e_recusado(pasta, tmp_path):
    p = Pasta(pasta)
    assert p.caminho("sub/a.md") == (pasta / "sub" / "a.md").resolve()
    for ruim in ("../fora.txt", "sub/../../fora.txt", str(tmp_path / "fora.txt")):
        with pytest.raises(ForaDaPasta, match="fora da pasta"):
            p.caminho(ruim)
    with pytest.raises(ForaDaPasta, match="chaves ou senhas"):
        p.caminho(".env")


def test_pastas_que_nao_podem_ser_escolhidas(pasta, tmp_path, monkeypatch):
    assert validar_pasta(str(pasta)) == pasta.resolve()
    with pytest.raises(ForaDaPasta, match="não existe"):
        validar_pasta(str(tmp_path / "nao-existe"))
    with pytest.raises(ForaDaPasta, match="caminho completo"):
        validar_pasta("relativa")
    with pytest.raises(ForaDaPasta, match="disco inteiro"):
        validar_pasta(Path(pasta.anchor).as_posix())
    # Os dados do Nicx e a pasta que os contém.
    casa = tmp_path / "casa"
    (casa / "nicx").mkdir(parents=True)
    monkeypatch.setenv("NICX_HOME", str(casa / "nicx"))
    for ruim in (casa / "nicx", casa):
        with pytest.raises(ForaDaPasta, match="próprio Nicx"):
            validar_pasta(str(ruim))


# ------------------------------------------------------------- ferramentas


def test_ler_listar_e_escrever_com_desfazer(pasta):
    tarefa, f = _ferramentas(pasta)
    ok, lista = f.executar("listar_arquivos", {})
    assert ok and "notas.txt" in lista and "[pasta] sub/" in lista
    assert f.executar("ler_arquivo", '{"caminho": "notas.txt"}') == (
        True,
        "compra 10,50\nvenda 30",
    )
    assert f.executar("escrever_arquivo", {"caminho": "notas.txt", "conteudo": "novo"})[
        0
    ]
    assert f.executar(
        "escrever_arquivo", {"caminho": "out/resumo.md", "conteudo": "# R"}
    )[0]
    assert f.executar("criar_pasta", {"caminho": "vazia"})[0]
    assert f.executar("mover", {"origem": "sub/a.md", "destino": "vazia"})[0]
    assert (pasta / "vazia" / "a.md").exists()

    problemas = ferramentas.desfazer(tarefa)
    assert problemas == []
    assert (pasta / "notas.txt").read_bytes() == b"compra 10,50\nvenda 30"
    assert not (pasta / "out" / "resumo.md").exists()
    assert (pasta / "sub" / "a.md").exists() and not (pasta / "vazia").exists()


def test_apagar_pede_confirmacao_e_vai_para_a_lixeira(pasta):
    perguntas = []
    tarefa, f = _ferramentas(pasta, confirmar=lambda t: perguntas.append(t) or False)
    ok, texto = f.executar("apagar", {"caminho": "notas.txt", "motivo": "duplicado"})
    assert ok and "não deixou" in texto and (pasta / "notas.txt").exists()
    assert "notas.txt" in perguntas[0] and "duplicado" in perguntas[0]

    tarefa, f = _ferramentas(pasta, confirmar=lambda t: True)
    assert f.executar("apagar", {"caminho": "notas.txt", "motivo": "x"})[0]
    assert not (pasta / "notas.txt").exists()
    ferramentas.desfazer(tarefa)
    assert (pasta / "notas.txt").exists()


def test_planilha_e_documento(pasta):
    tarefa, f = _ferramentas(pasta)
    abas = [
        {
            "nome": "Resumo",
            "linhas": [["Item", "Valor", "CEP"], ["compra", "10,50", "01310"]],
        }
    ]
    ok, texto = f.executar("criar_planilha", {"caminho": "resumo.xlsx", "abas": abas})
    assert ok, texto
    ok, lido = f.executar("ler_arquivo", {"caminho": "resumo.xlsx"})
    assert "[aba Resumo]" in lido and "compra\t10.5\t01310" in lido
    ok, texto = f.executar(
        "criar_documento",
        {
            "caminho": "relatorio.docx",
            "titulo": "Relatório",
            "texto": "# Parte\n- item um\ntexto",
        },
    )
    assert ok, texto
    ok, lido = f.executar("ler_arquivo", {"caminho": "relatorio.docx"})
    assert "Relatório" in lido and "item um" in lido
    assert not f.executar("criar_planilha", {"caminho": "x.csv", "abas": abas})[0]


def test_ferramenta_com_argumento_ruim_nao_quebra(pasta):
    _t, f = _ferramentas(pasta)
    assert f.executar("ler_arquivo", "{nao e json") == (
        False,
        "argumentos inválidos (mande um objeto JSON)",
    )
    ok, texto = f.executar("ler_arquivo", {"arquivo": "x"})
    assert not ok and "argumentos errados" in texto
    assert not f.executar("formatar_disco", {})[0]
    assert not f.executar("ler_arquivo", {"caminho": "../../segredo"})[0]


# --------------------------------------------------------------- executor


class MotorFalso:
    """Responde por roteiro: plano em JSON e, por passo, chamadas e frase final."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def generate(self, mensagens, model, **kw):
        self.pedidos.append((mensagens, kw))
        r = self.respostas.pop(0) if self.respostas else {"content": "pronto"}
        return r() if callable(r) else r


def _chamada(nome, **args):
    return {
        "content": "",
        "tool_calls": [{"id": nome, "name": nome, "arguments": json.dumps(args)}],
    }


def test_extrair_passos():
    assert executor.extrair_passos('{"passos": ["ler", "  escrever  "]}') == [
        "ler",
        "escrever",
    ]
    assert executor.extrair_passos('Claro! ["a", {"descricao": "b"}]') == ["a", "b"]
    assert executor.extrair_passos("sem json") == []
    assert (
        len(
            executor.extrair_passos(json.dumps({"passos": [str(i) for i in range(20)]}))
        )
        == 7
    )


def _esperar(tarefa_id, estados, segundos=10):
    fim = time.time() + segundos
    while time.time() < fim:
        t = servico.ver(tarefa_id)
        if t["estado"] in estados:
            return t
        time.sleep(0.05)
    raise AssertionError(
        f"tarefa não chegou em {estados}: {servico.ver(tarefa_id)['estado']}"
    )


def test_fluxo_completo_planejar_aprovar_executar_desfazer(pasta):
    motor = MotorFalso(
        [
            {"content": '{"passos": ["ver os arquivos", "escrever o resumo"]}'},
            _chamada("listar_arquivos"),
            {"content": "Vi notas.txt e a pasta sub."},
            _chamada(
                "escrever_arquivo",
                caminho="resumo.md",
                conteudo="# Resumo\ncompra e venda",
            ),
            {"content": "Escrevi resumo.md."},
        ]
    )
    t = servico.criar(str(pasta), "faz um resumo das notas", motor, "m")
    t = _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})
    assert [p["descricao"] for p in t["plano"]] == [
        "ver os arquivos",
        "escrever o resumo",
    ]
    assert not (pasta / "resumo.md").exists()  # nada antes de aprovar

    servico.aprovar(t["id"], None, motor, "m")
    t = _esperar(t["id"], {modelo.CONCLUIDA})
    assert (pasta / "resumo.md").read_text(encoding="utf-8").startswith("# Resumo")
    assert [p["estado"] for p in t["plano"]] == ["feito", "feito"]
    assert "Escrevi resumo.md." in t["resumo"] and "resumo.md" in t["arquivos_mudados"]
    # Ferramentas foram oferecidas no passo e o plano pediu JSON.
    assert motor.pedidos[0][1].get("response_format") == {"type": "json_object"}
    assert motor.pedidos[1][1].get("tools")

    t = servico.desfazer(t["id"])
    assert t["estado"] == modelo.DESFEITA and not (pasta / "resumo.md").exists()


def test_plano_editado_pela_pessoa(pasta):
    motor = MotorFalso([{"content": '{"passos": ["a", "b", "c"]}'}])
    t = servico.criar(str(pasta), "tarefa qualquer", motor, "m")
    _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})
    servico.aprovar(t["id"], ["só isto"], MotorFalso([{"content": "feito"}]), "m")
    t = _esperar(t["id"], {modelo.CONCLUIDA})
    assert [p["descricao"] for p in t["plano"]] == ["só isto"]


def test_apagar_espera_a_pessoa(pasta):
    motor = MotorFalso(
        [
            {"content": '{"passos": ["apagar notas"]}'},
            _chamada("apagar", caminho="notas.txt", motivo="pediram"),
            {"content": "Apaguei notas.txt."},
        ]
    )
    t = servico.criar(str(pasta), "apaga as notas", motor, "m")
    _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})
    servico.aprovar(t["id"], None, motor, "m")
    t = _esperar(t["id"], {modelo.AGUARDANDO_CONFIRMACAO})
    assert "notas.txt" in t["pergunta"]["texto"]
    assert (pasta / "notas.txt").exists()
    servico.responder(t["id"], True)
    _esperar(t["id"], {modelo.CONCLUIDA})
    assert not (pasta / "notas.txt").exists()


def test_parar_no_meio(pasta):
    import threading

    solta = threading.Event()

    def lento():
        solta.wait(5)
        return {
            "content": "",
            "tool_calls": [{"id": "x", "name": "listar_arquivos", "arguments": "{}"}],
        }

    motor = MotorFalso([{"content": '{"passos": ["um", "dois"]}'}, lento])
    t = servico.criar(str(pasta), "tarefa longa", motor, "m")
    _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})
    servico.aprovar(t["id"], None, motor, "m")
    _esperar(t["id"], {modelo.EXECUTANDO})
    parada = None

    def parar():
        nonlocal parada
        parada = servico.parar(t["id"])

    th = threading.Thread(target=parar)
    th.start()
    time.sleep(0.2)
    solta.set()
    th.join(10)
    t = _esperar(t["id"], {modelo.PARADA})
    assert t["plano"][0]["estado"] == "pendente"  # pode retomar depois


def test_uma_tarefa_por_vez(pasta):
    import threading

    solta = threading.Event()
    motor = MotorFalso([lambda: (solta.wait(5), {"content": '{"passos": ["a"]}'})[1]])
    t = servico.criar(str(pasta), "primeira tarefa", motor, "m")
    with pytest.raises(servico.TrabalhoErro, match="já há uma tarefa"):
        servico.criar(str(pasta), "segunda tarefa", MotorFalso([]), "m")
    solta.set()
    _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})


def test_rotas(pasta):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.trabalho import router

    app = FastAPI()
    app.include_router(router)
    app.state.engine = MotorFalso([{"content": '{"passos": ["olhar"]}'}])
    app.state.model = "m"
    http = TestClient(app)
    r = http.post(
        "/v1/trabalho", json={"pasta": str(pasta), "pedido": "organiza a pasta"}
    )
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    _esperar(tid, {modelo.AGUARDANDO_APROVACAO})
    assert http.get(f"/v1/trabalho/{tid}").json()["plano"][0]["descricao"] == "olhar"
    assert any(t["id"] == tid for t in http.get("/v1/trabalho").json()["tarefas"])
    ruim = http.post(
        "/v1/trabalho", json={"pasta": "C:/", "pedido": "organiza a pasta"}
    )
    assert ruim.status_code == 409
    assert (
        http.post(
            f"/v1/trabalho/{tid}/responder", json={"confirmado": True}
        ).status_code
        == 409
    )


def test_passo_sem_plano_legivel_vira_tarefa_inteira(pasta):
    _t, f = _ferramentas(pasta)
    tarefa = Tarefa(id=modelo.novo_id(), pasta=str(pasta), pedido="faça X")
    passos = executor.planejar(tarefa, MotorFalso([{"content": "não sei"}]), "m", f)
    assert passos == [Passo(descricao="faça X")]


@pytest.mark.parametrize("limite, continua", [(None, True), (0, False)])
def test_passos_continuam_a_conversa_ate_o_limite(pasta, monkeypatch, limite, continua):
    if limite is not None:
        monkeypatch.setattr(executor, "LIMITE_CONVERSA", limite)
    motor = MotorFalso(
        [
            {"content": '{"passos": ["ver os arquivos", "escrever o resumo"]}'},
            _chamada("listar_arquivos"),
            {"content": "Vi notas.txt e a pasta sub."},
            {"content": "Resumo pronto."},
        ]
    )
    t = servico.criar(str(pasta), "faz um resumo das notas", motor, "m")
    _esperar(t["id"], {modelo.AGUARDANDO_APROVACAO})
    servico.aprovar(t["id"], None, motor, "m")
    _esperar(t["id"], {modelo.CONCLUIDA})
    passo2 = motor.pedidos[3][0]
    textos = [m.content for m in passo2]
    assert ("Vi notas.txt e a pasta sub." in textos) is continua
    assert any(x.endswith("passo 2: escrever o resumo") for x in textos)
    assert textos[-1] == "Resumo pronto."  # a resposta fica para o próximo passo
