"""Rotas /v1/resumo: o resumo do dia, refinado ou não, e a config [resumo]."""

from __future__ import annotations

import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.acoes import agenda, calendarios
from nicx.nucleo.config import NicxConfig
from nicx.resumo import montagem
from nicx.servidor.rotas.resumo import router

NOW = datetime(2026, 10, 30, 18, 30)


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("NICX_HOME", str(home))
    monkeypatch.setenv("NICX_CONFIG", str(home / "config.toml"))
    cfg = SimpleNamespace(calendario_padrao="windows", fuso="America/Sao_Paulo")
    monkeypatch.setattr(calendarios, "_config_agenda", lambda: cfg)
    monkeypatch.setattr(calendarios, "eventos_conectados", lambda day: [])
    monkeypatch.setattr(montagem, "agora_local", lambda: NOW)
    monkeypatch.setitem(sys.modules, "nicx.projetos", None)
    return home


class _Motor:
    is_cloud = False

    def __init__(
        self, resposta="<think>pensando</think> Hoje foi tranquilo.", erro=None
    ):
        self.resposta = resposta
        self.erro = erro
        self.pedidos: list = []

    def generate(self, messages, *, model, **kwargs):
        self.pedidos.append((messages, model))
        if self.erro:
            raise self.erro
        return {"content": self.resposta}


@pytest.fixture
def app(home):
    app = FastAPI()
    app.state.config = NicxConfig()
    app.state.config._config_path = home / "config.toml"
    app.include_router(router)
    return app


def test_resumo_de_hoje(home, app):
    agenda.add("dentista", datetime(2026, 10, 31, 9, 0), now=datetime(2026, 10, 1))
    data = TestClient(app).get("/v1/resumo").json()
    assert data["dia"] == "2026-10-30" and data["idioma"] == "pt-BR"
    assert data["texto"].endswith("Amanhã você tem: dentista às 9h.")
    assert data["texto_pendente"].startswith("Nada ficou pendente hoje.")
    assert data["secoes"]["compromissos_seguinte"] == [
        {"titulo": "dentista", "hora": "09:00"}
    ]
    assert data["refinado"] is False


def test_resumo_de_um_dia_e_idioma(home, app):
    client = TestClient(app)
    data = client.get("/v1/resumo", params={"dia": "2026-10-29", "idioma": "en"}).json()
    assert data["dia"] == "2026-10-29"
    assert data["texto"].startswith("Summary of yesterday.")
    assert client.get("/v1/resumo", params={"dia": "30/10"}).status_code == 422


def test_refinar_com_o_modelo_local(home, app):
    motor = _Motor()
    app.state.engine, app.state.model = motor, "qwen3.5:4b"
    data = TestClient(app).get("/v1/resumo", params={"refinar": "true"}).json()
    assert data == {**data, "texto": "Hoje foi tranquilo.", "refinado": True}
    mensagens, modelo = motor.pedidos[0]
    assert modelo == "qwen3.5:4b"
    assert "Resumo do seu dia." in mensagens[0].content


def test_refinar_em_outro_idioma_pede_o_idioma(home, app):
    motor = _Motor()
    app.state.engine, app.state.model = motor, "qwen3.5:4b"
    TestClient(app).get("/v1/resumo", params={"refinar": "true", "idioma": "fr"})
    assert "Responda em francês" in motor.pedidos[0][0][0].content


def test_refinar_com_falha_fica_o_texto(home, app):
    app.state.engine = _Motor(erro=RuntimeError("Ollama fora"))
    app.state.model = "qwen3.5:4b"
    data = TestClient(app).get("/v1/resumo", params={"refinar": "true"}).json()
    assert data["refinado"] is False
    assert data["texto"].startswith("Resumo do seu dia.")


def test_refinar_nunca_usa_a_nuvem(home, app):
    motor = _Motor()
    app.state.engine, app.state.model = motor, "openai/gpt-4o"
    data = TestClient(app).get("/v1/resumo", params={"refinar": "true"}).json()
    assert data["refinado"] is False and motor.pedidos == []
    nuvem = _Motor()
    nuvem.is_cloud = True
    app.state.engine, app.state.model = nuvem, "qwen3.5:4b"
    TestClient(app).get("/v1/resumo", params={"refinar": "true"})
    assert nuvem.pedidos == []


def test_refinar_sem_motor(home, app):
    data = TestClient(app).get("/v1/resumo", params={"refinar": "true"}).json()
    assert data["refinado"] is False


def test_config_padrao(home, app):
    data = TestClient(app).get("/v1/resumo/config").json()
    assert data == {
        "ativo": False,
        "hora": "18:00",
        "falar": True,
        "notificar": True,
        "dias": ["seg", "ter", "qua", "qui", "sex"],
        "opcoes_dias": ["seg", "ter", "qua", "qui", "sex", "sab", "dom"],
        "ultimo_envio": None,
    }


def test_config_salva_e_aplica(home, app):
    client = TestClient(app)
    data = client.put(
        "/v1/resumo/config",
        json={
            "ativo": True,
            "hora": "7:05",
            "dias": ["dom", "sab", "seg"],
            "falar": False,
        },
    ).json()
    assert data["ativo"] is True and data["hora"] == "07:05"
    assert data["dias"] == ["seg", "sab", "dom"] and data["falar"] is False
    assert app.state.config.resumo.hora == "07:05"
    texto = (home / "config.toml").read_text(encoding="utf-8")
    assert "[resumo]" in texto and 'hora = "07:05"' in texto


@pytest.mark.parametrize(
    "corpo", [{"hora": "18h"}, {"hora": "24:00"}, {"dias": ["segunda"]}]
)
def test_config_recusa_valores_ruins(home, app, corpo):
    response = TestClient(app).put("/v1/resumo/config", json=corpo)
    assert response.status_code == 422
    assert not (home / "config.toml").exists()


def test_rota_no_app_do_servidor():
    from unittest.mock import MagicMock

    from nicx.servidor.app import create_app

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    caminhos = {r.path for r in create_app(MagicMock(), "m", config=cfg).routes}
    assert {"/v1/resumo", "/v1/resumo/config"} <= caminhos
