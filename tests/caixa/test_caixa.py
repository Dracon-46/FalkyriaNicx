"""Caixa de entrada: junta aprovações, modo Trabalho e agentes; dispensa avisos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from nicx.caixa import servico
from nicx.trabalho import modelo
from nicx.trabalho.modelo import Passo, Tarefa


@dataclass
class Acao:
    id: str
    action_type: str = "enviar_email"
    description: str = "Enviar o relatório para a equipe"
    tier: str = "medium"
    payload: dict = field(default_factory=dict)
    created_at: str = "2026-11-25T10:00:00+00:00"


class Aprovacoes:
    def __init__(self, *acoes):
        self.acoes = list(acoes)

    def expire_stale(self):
        pass

    def list_pending(self):
        return self.acoes


class Agentes:
    def __init__(self, *agentes):
        self.agentes = list(agentes)

    def list_agents(self):
        return self.agentes


AGORA = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def _tarefa(estado: str, **kw) -> Tarefa:
    t = Tarefa(
        id=modelo.novo_id(),
        pasta="C:/x",
        pedido=kw.pop("pedido", "organiza a pasta"),
        estado=estado,
        **kw,
    )
    modelo.salvar(t)
    return t


@pytest.fixture(autouse=True)
def _limpo():
    import shutil

    shutil.rmtree(modelo.pasta_dados(), ignore_errors=True)
    servico._arquivo_vistos().unlink(missing_ok=True)
    yield
    shutil.rmtree(modelo.pasta_dados(), ignore_errors=True)
    servico._arquivo_vistos().unlink(missing_ok=True)


def _simular(monkeypatch, *tarefas):
    """Tarefas como a lista do serviço as devolve (uma pode estar rodando)."""
    from nicx.trabalho import servico as trabalho

    monkeypatch.setattr(trabalho, "listar", lambda: [t.para_dict() for t in tarefas])


def test_junta_as_fontes_e_separa_decisoes_de_avisos(monkeypatch):
    pergunta = _tarefa(
        modelo.AGUARDANDO_CONFIRMACAO, pergunta={"texto": "Apagar velho.txt?"}
    )
    plano = _tarefa(modelo.AGUARDANDO_APROVACAO, plano=[Passo("ler"), Passo("criar")])
    feita = _tarefa(modelo.CONCLUIDA, resumo="Criei gastos.xlsx.")
    falhou = _tarefa(modelo.ERRO, erro="o modelo não respondeu")
    agente = {
        "id": "a1",
        "name": "Monitor de preços",
        "status": "error",
        "updated_at": (AGORA - timedelta(minutes=5)).timestamp(),
        "current_activity": "falhou ao abrir o site",
    }
    for t in (pergunta, plano, feita, falhou):
        t.atualizado_em = (AGORA - timedelta(hours=1)).isoformat()
    _simular(monkeypatch, pergunta, plano, feita, falhou)
    caixa = servico.montar(
        aprovacoes=Aprovacoes(Acao("x1")),
        agentes=Agentes(agente, {"id": "a2", "name": "ok", "status": "running"}),
        agora=AGORA,
    )
    tipos = {i["tipo"]: i for i in caixa["decisoes"]}
    assert set(tipos) == {"aprovacao", "trabalho_pergunta", "trabalho_plano"}
    assert tipos["trabalho_pergunta"]["texto"] == "Apagar velho.txt?"
    assert tipos["trabalho_pergunta"]["ref"] == pergunta.id
    assert tipos["trabalho_plano"]["texto"] == "ler\ncriar"
    assert tipos["trabalho_plano"]["ref"] == plano.id

    avisos = {i["tipo"]: i for i in caixa["avisos"]}
    assert set(avisos) == {"trabalho_concluida", "trabalho_erro", "agente_erro"}
    assert avisos["trabalho_concluida"]["ref"] == feita.id
    assert avisos["trabalho_erro"]["texto"] == falhou.erro
    assert avisos["agente_erro"]["link"] == "/agents"

    atv = caixa["atividade"]
    assert atv["esperando"] == 3
    assert atv["trabalhando"] is True  # pergunta pendente + agente rodando
    assert atv["ultimo_concluido"] and atv["ultimo_erro"]


def test_dispensar_esconde_o_aviso_mas_nao_a_decisao():
    _tarefa(modelo.CONCLUIDA)
    _tarefa(modelo.AGUARDANDO_APROVACAO, plano=[Passo("a")])
    caixa = servico.montar()
    aviso = caixa["avisos"][0]["id"]
    decisao = caixa["decisoes"][0]["id"]
    assert servico.dispensar([aviso, decisao, aviso]) == 1
    depois = servico.montar()
    assert depois["avisos"] == []
    assert [d["id"] for d in depois["decisoes"]] == [decisao]


def test_avisos_velhos_somem(monkeypatch):
    velha = _tarefa(modelo.ERRO, erro="x")
    nova = _tarefa(modelo.CONCLUIDA)
    velha.atualizado_em = (AGORA - timedelta(days=8)).isoformat()
    nova.atualizado_em = (AGORA - timedelta(hours=1)).isoformat()
    _simular(monkeypatch, velha, nova)
    caixa = servico.montar(agora=AGORA)
    assert [a["tipo"] for a in caixa["avisos"]] == ["trabalho_concluida"]


def test_dispensar_todos():
    _tarefa(modelo.CONCLUIDA)
    _tarefa(modelo.ERRO, erro="x")
    assert servico.dispensar_avisos() == 2
    assert servico.montar()["avisos"] == []


def test_fonte_quebrada_nao_derruba_a_caixa():
    class Quebrada:
        def expire_stale(self):
            raise RuntimeError("banco travado")

        def list_agents(self):
            raise RuntimeError("banco travado")

    caixa = servico.montar(aprovacoes=Quebrada(), agentes=Quebrada(), agora=AGORA)
    assert caixa["decisoes"] == [] and caixa["avisos"] == []
    assert caixa["atividade"]["trabalhando"] is False


def test_rotas():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.caixa import router

    _tarefa(modelo.CONCLUIDA)
    app = FastAPI()
    app.include_router(router)
    http = TestClient(app)
    r = http.get("/v1/caixa")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert len(corpo["avisos"]) == 1 and "atividade" in corpo
    r = http.post("/v1/caixa/dispensar", json={"todos": True})
    assert r.json() == {"dispensados": 1}
    assert http.get("/v1/caixa").json()["avisos"] == []
