"""Rotinas: recorrência, frases, execução, agendador, desfazer e rotas."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.acoes import confirmacao, handle, lembretes, notas, parse
from nicx.historico.desfazer import desfazer
from nicx.rotinas import agendador, armazenamento, servico
from nicx.rotinas.modelo import Agenda, Passo, Rotina, RotinaInvalida, validar
from nicx.rotinas.recorrencia import interpretar

SEGUNDA_9H = datetime(2026, 11, 2, 9, 0)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"
    confirmacao.drop()


@pytest.mark.parametrize(
    ("texto", "dias", "hora"),
    [
        ("toda segunda as 9h", ["seg"], "09:00"),
        (
            "todo dia as 7h30",
            ["seg", "ter", "qua", "qui", "sex", "sab", "dom"],
            "07:30",
        ),
        ("de segunda a sexta as 8", ["seg", "ter", "qua", "qui", "sex"], "08:00"),
        ("toda segunda e quarta as 18h", ["seg", "qua"], "18:00"),
        ("todas as tercas as 6 da tarde", ["ter"], "18:00"),
        ("fim de semana as 10", ["sab", "dom"], "10:00"),
        ("every weekday at 8 am", ["seg", "ter", "qua", "qui", "sex"], "08:00"),
        (
            "todos los dias a las 7",
            ["seg", "ter", "qua", "qui", "sex", "sab", "dom"],
            "07:00",
        ),
        ("du lundi au vendredi a 8h", ["seg", "ter", "qua", "qui", "sex"], "08:00"),
    ],
)
def test_recorrencia(texto, dias, hora):
    assert interpretar(texto) == Agenda(dias=dias, hora=hora)


@pytest.mark.parametrize("texto", ["todo dia", "abre o chrome", "segunda", "as 9"])
def test_nao_e_recorrencia(texto):
    assert interpretar(texto) is None


def _criar(
    frase="cria a rotina preparar estudo: anota Revisar Cálculo, timer de 50 minutos",
):
    return handle(frase)


def test_cria_por_frase_e_roda_pelo_nome():
    saida = _criar(
        "cria a rotina preparar estudo: anota Revisar Cálculo,"
        " timer de 50 minutos, toda segunda às 9h"
    )
    assert saida.ok and "2 passos" in saida.message and "segunda" in saida.message
    (rotina,) = armazenamento.listar()
    assert rotina.agenda == Agenda(["seg"], "09:00")
    assert [p.kind for p in rotina.passos] == ["note_add", "remind"]
    assert rotina.passos[1].minutos == 50
    assert handle("Preparar estudo!").ok  # a frase exata do nome roda
    assert notas.all_notes() == ["Revisar Cálculo"]  # o texto original, com maiúsculas
    assert handle("roda a rotina preparar estudo").ok
    assert len(lembretes.pending()) == 2
    assert parse("minhas rotinas").op == "listar"


def test_passos_proibidos_e_desconhecidos():
    assert "não podem" in _criar("cria a rotina x: desliga o pc").message
    assert "Não entendi" in _criar("cria a rotina y: faz um bolo").message
    assert "Faltaram" in _criar("cria a rotina z:").message
    assert armazenamento.listar() == []


def test_nome_repetido():
    _criar()
    assert "Já existe" in _criar().message


def test_e_entre_comandos():
    saida = _criar("cria a rotina dupla: abre o chrome e aumenta o volume")
    assert saida.ok, saida.message
    assert [p.kind for p in armazenamento.listar()[0].passos] == ["open", "volume"]


def test_site():
    lido = servico.interpretar_passos("abre github.com/falkyria")
    assert [(p.kind, p.target) for p in lido["passos"]] == [
        ("open_url", "https://github.com/falkyria")
    ]


def test_validacao():
    with pytest.raises(RotinaInvalida):
        validar(Rotina(nome="x", passos=[Passo("power", op="shutdown")]))
    with pytest.raises(RotinaInvalida):
        validar(
            Rotina(nome="x", passos=[Passo("open_url", target="javascript:alert(1)")])
        )
    with pytest.raises(RotinaInvalida):
        validar(Rotina(nome="", passos=[Passo("note_add", target="x")]))


def test_apagar_e_desfazer():
    _criar()
    assert "apagada" in handle("apaga a rotina preparar estudo").message
    assert armazenamento.listar() == []
    assert desfazer()[0]
    assert [r.nome for r in armazenamento.listar()] == ["preparar estudo"]


def test_modo_foco_pronto(monkeypatch):
    feitos = []
    from nicx.acoes import sistema

    def falso(acao, idioma=None, **_kw):
        feitos.append(acao.kind)
        return sistema.Outcome(True, "ok")

    monkeypatch.setattr(sistema, "run", falso)  # o servico chama sistema.run
    saida = handle("ativa o modo foco")
    assert saida.ok and feitos == ["close", "volume", "remind"]


def test_agendador(monkeypatch):
    rodadas = []
    monkeypatch.setattr(agendador, "_rodar", lambda r: rodadas.append(r.nome))
    monkeypatch.setattr(agendador.threading, "Thread", _ThreadNaHora)
    armazenamento.criar(
        Rotina(
            nome="aula",
            passos=[Passo("note_add", target="x")],
            agenda=Agenda(["seg"], "09:00"),
        )
    )
    assert agendador.verificar(datetime(2026, 11, 2, 8, 59)) == []
    assert len(agendador.verificar(SEGUNDA_9H)) == 1
    assert agendador.verificar(SEGUNDA_9H) == []  # uma vez por dia
    assert (
        agendador.verificar(datetime(2026, 11, 9, 11, 30)) == []
    )  # passou da janela de 2 h
    assert agendador.verificar(datetime(2026, 11, 3, 9, 0)) == []  # terça não
    assert rodadas == ["aula"]


class _ThreadNaHora:
    def __init__(self, target, args, **_kw):
        self._alvo, self._args = target, args

    def start(self):
        self._alvo(*self._args)


@pytest.fixture
def client():
    from nicx.servidor.rotas.rotinas import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rotas(client):
    corpo = {
        "nome": "manhã",
        "passos": [{"kind": "note_add", "target": "bom dia"}],
        "agenda": {"dias": ["seg"], "hora": "07:00"},
    }
    criada = client.post("/v1/rotinas", json=corpo).json()
    assert criada["agenda"] == {"dias": ["seg"], "hora": "07:00"}
    assert client.post("/v1/rotinas", json=corpo).status_code == 409
    assert (
        client.post(
            "/v1/rotinas", json={**corpo, "nome": "x", "passos": [{"kind": "power"}]}
        ).status_code
        == 400
    )
    dados = client.get("/v1/rotinas").json()
    assert [r["nome"] for r in dados["rotinas"]] == ["manhã"] and dados["modelos"][0][
        "id"
    ] == "modelo-foco"
    assert client.post(f"/v1/rotinas/{criada['id']}/executar", json={}).json()["ok"]
    assert notas.all_notes() == ["bom dia"]
    novo = client.put(
        f"/v1/rotinas/{criada['id']}", json={**corpo, "ativa": False}
    ).json()
    assert novo["ativa"] is False and novo["id"] == criada["id"]
    lido = client.post(
        "/v1/rotinas/interpretar",
        json={"texto": "anota oi, timer de 5 minutos, todo dia às 8"},
    ).json()
    assert [p["kind"] for p in lido["passos"]] == ["note_add", "remind"] and lido[
        "agenda"
    ]["hora"] == "08:00"
    opcoes = client.get("/v1/rotinas/opcoes").json()
    assert "open_url" in opcoes["tipos"] and opcoes["apps"]
    assert client.delete(f"/v1/rotinas/{criada['id']}").json()["ok"]
    assert client.delete(f"/v1/rotinas/{criada['id']}").status_code == 404


def test_textos_com_as_mesmas_chaves():
    from nicx.rotinas import textos

    chaves = textos.chaves()
    assert all(c == chaves["pt-BR"] for c in chaves.values())
