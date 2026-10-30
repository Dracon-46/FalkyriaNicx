"""Rotas /v1/projetos e os pedidos de projeto pela rota do chat."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from nicx.contexto.montagem import FIM, INICIO  # noqa: E402
from nicx.projetos import continuar, deteccao  # noqa: E402
from nicx.projetos.armazenamento import Projetos  # noqa: E402
from nicx.servidor.rotas.projetos import router  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    home = tmp_path / "nicx"
    home.mkdir()
    monkeypatch.setenv("NICX_HOME", str(home))
    monkeypatch.setattr(deteccao, "sinal_da_janela", lambda info=None: None)
    monkeypatch.setattr(continuar, "coletar", lambda projeto: continuar.Sinais())
    deteccao.esquecer_intervalos()
    return home


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_crud_de_projeto(client, tmp_path):
    assert client.get("/v1/projetos").json() == {"projetos": [], "atual": None}
    criado = client.post(
        "/v1/projetos",
        json={"nome": "Lumen", "objetivo": "Dados", "pastas": [str(tmp_path)]},
    )
    assert criado.status_code == 201
    pid = criado.json()["id"]
    assert client.post("/v1/projetos", json={"nome": "lumen"}).status_code == 409
    assert client.post("/v1/projetos", json={"nome": ""}).status_code == 422

    lista = client.get("/v1/projetos").json()["projetos"]
    assert lista == [
        {
            "id": pid,
            "nome": "Lumen",
            "estado": "",
            "objetivo": "Dados",
            "ultima_atividade": lista[0]["ultima_atividade"],
            "pendencias_abertas": 0,
            "arquivado": False,
        }
    ]

    mudado = client.patch(
        f"/v1/projetos/{pid}",
        json={
            "estado": "API pronta",
            "nome": "Lumen Dados",
            "proximos_passos": ["Login"],
        },
    ).json()
    assert mudado["estado"] == "API pronta"
    assert mudado["nome"] == "Lumen Dados"
    assert mudado["proximos_passos"] == ["Login"]

    com_decisao = client.post(
        f"/v1/projetos/{pid}/decisoes", json={"texto": "Postgres"}
    )
    assert com_decisao.status_code == 201
    assert com_decisao.json()["decisoes"][0]["texto"] == "Postgres"

    detalhe = client.post(
        f"/v1/projetos/{pid}/pendencias", json={"texto": "Domínio"}
    ).json()
    pend = detalhe["pendencias"][0]["id"]
    feita = client.patch(
        f"/v1/projetos/{pid}/pendencias/{pend}", json={"feita": True}
    ).json()
    assert feita["pendencias"][0]["feita"] is True
    assert feita["pendencias"][0]["feita_em"]
    reaberta = client.patch(
        f"/v1/projetos/{pid}/pendencias/{pend}",
        json={"feita": False, "texto": "Domínio .br"},
    ).json()
    assert reaberta["pendencias"][0]["feita"] is False
    assert reaberta["pendencias"][0]["texto"] == "Domínio .br"
    assert client.get("/v1/projetos").json()["projetos"][0]["pendencias_abertas"] == 1
    assert (
        client.patch(
            f"/v1/projetos/{pid}/pendencias/xx", json={"feita": True}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/v1/projetos/{pid}/pendencias/{pend}").json()["pendencias"]
        == []
    )

    sinais = client.get(f"/v1/projetos/{pid}/sinais").json()
    assert sinais["git"] is None  # tmp_path não é git
    assert isinstance(sinais["recentes"], list)

    assert client.patch(f"/v1/projetos/{pid}", json={"arquivado": True}).json()[
        "arquivado"
    ]
    assert client.get("/v1/projetos").json()["projetos"] == []
    assert len(client.get("/v1/projetos?arquivados=true").json()["projetos"]) == 1
    assert client.delete(f"/v1/projetos/{pid}").json() == {"ok": True}
    assert client.get(f"/v1/projetos/{pid}").status_code == 404
    assert client.delete(f"/v1/projetos/{pid}").status_code == 404


def test_lista_diz_o_projeto_da_janela(client, tmp_path, monkeypatch):
    loja = Projetos()
    lumen = loja.criar("Lumen", pastas=[str(tmp_path)])
    loja.criar("Ascend")
    monkeypatch.setattr(
        deteccao,
        "sinal_da_janela",
        lambda info=None: deteccao.SinalJanela(caminho=str(tmp_path / "a.py")),
    )
    assert client.get("/v1/projetos").json()["atual"] == lumen.id


# --- Pela rota do chat ---------------------------------------------------------


def _chat_client():
    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.app import create_app

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.context_from_memory = False
    cfg.contexto.ativo = False
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "Você parou na tela de login. Quer continuar por ali?",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    memory = MagicMock()
    memory.list_facts.return_value = []
    app = create_app(engine, "m", config=cfg, memory_service=memory)
    return TestClient(app), engine, memory


def _texto(resposta):
    return resposta.json()["choices"][0]["message"]["content"]


def test_chat_responde_na_hora_sem_modelo():
    client, engine, _ = _chat_client()
    body = {
        "model": "m",
        "messages": [{"role": "user", "content": "cria o projeto Lumen"}],
    }
    assert (
        _texto(client.post("/v1/chat/completions", json=body))
        == 'Projeto "Lumen" criado.'
    )
    # "anota no projeto..." é do projeto, não vira uma anotação solta.
    body["messages"][0]["content"] = (
        "anota no projeto Lumen que decidimos usar Postgres"
    )
    assert _texto(client.post("/v1/chat/completions", json=body)) == (
        "Anotado no projeto Lumen: Usar Postgres."
    )
    body["messages"][0]["content"] = "what are my projects?"
    body["language"] = "en"
    assert _texto(client.post("/v1/chat/completions", json=body)) == (
        "Your projects: Lumen (nothing pending)."
    )
    engine.generate.assert_not_called()


def test_chat_continuar_manda_o_resumo_ao_modelo():
    Projetos().criar("Lumen")
    Projetos().atualizar_estado(Projetos().buscar("Lumen").id, "Falta a tela de login")
    client, engine, memory = _chat_client()
    body = {
        "model": "m",
        "messages": [{"role": "user", "content": "continue de onde parei"}],
    }
    resposta = client.post("/v1/chat/completions", json=body)
    assert _texto(resposta).startswith("Você parou")
    mensagens = engine.generate.call_args.args[0]
    ultima = mensagens[-1].content
    assert ultima.startswith("continue de onde parei\n\n" + INICIO)
    assert "Estado: Falta a tela de login" in ultima
    assert ultima.index(FIM) < ultima.index(continuar.AVISO)
    # Não vai para a memória automática.
    memory.submit.assert_not_called()


def test_chat_continuar_com_modelo_da_nuvem_recusa(monkeypatch):
    Projetos().criar("Lumen")
    from nicx.servidor.rotas import nuvem

    monkeypatch.setattr(nuvem, "is_cloud_model", lambda model: True)
    client, engine, _ = _chat_client()
    body = {
        "model": "m",
        "messages": [{"role": "user", "content": "continue de onde parei"}],
    }
    assert "só vão para modelos locais" in _texto(
        client.post("/v1/chat/completions", json=body)
    )
    engine.generate.assert_not_called()
