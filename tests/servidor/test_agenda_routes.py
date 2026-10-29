"""Rotas /v1/agenda/config: calendário padrão e contas conectadas."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.acoes import calendarios
from nicx.nucleo.config import NicxConfig
from nicx.servidor.rotas.agenda import router


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("NICX_HOME", str(home))
    monkeypatch.setenv("NICX_CONFIG", str(home / "config.toml"))
    cfg = SimpleNamespace(calendario_padrao="windows", fuso="America/Sao_Paulo")
    monkeypatch.setattr(calendarios, "_config_agenda", lambda: cfg)
    return home


@pytest.fixture
def app():
    app = FastAPI()
    app.state.config = NicxConfig()
    app.include_router(router)
    return app


def test_get_reports_default_and_accounts(home, app):
    connectors = home / "connectors"
    connectors.mkdir()
    (connectors / "google.json").write_text(
        json.dumps(
            {
                "access_token": "t",
                "scope": "https://www.googleapis.com/auth/calendar.readonly",
            }
        ),
        encoding="utf-8",
    )
    data = TestClient(app).get("/v1/agenda/config").json()
    assert data["calendario_padrao"] == "windows"
    assert data["opcoes"] == ["windows", "google", "outlook", "outlook_trabalho"]
    assert data["google_conectado"] is True and data["google_escrita"] is False
    assert data["outlook_conectado"] is False


def test_put_saves_and_applies(home, app):
    client = TestClient(app)
    data = client.put(
        "/v1/agenda/config", json={"calendario_padrao": "outlook_trabalho"}
    ).json()
    assert data["calendario_padrao"] == "outlook_trabalho"
    assert app.state.config.agenda.calendario_padrao == "outlook_trabalho"
    text = (home / "config.toml").read_text(encoding="utf-8")
    assert 'calendario_padrao = "outlook_trabalho"' in text


def test_put_rejects_unknown_calendar(home, app):
    response = TestClient(app).put(
        "/v1/agenda/config", json={"calendario_padrao": "yahoo"}
    )
    assert response.status_code == 422
    assert not (home / "config.toml").exists()
