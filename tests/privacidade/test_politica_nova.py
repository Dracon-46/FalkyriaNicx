"""Política de privacidade nova: o app pergunta de novo e mostra que mudou.

Até a resposta vale a escolha anterior (LGPD, art. 8, § 6: informar a mudança
e deixar revogar). Confirmar de novo fica registrado com a versão aceita.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomllib
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.nucleo.config import NicxConfig
from nicx.nucleo.events import EventBus
from nicx.privacidade import POLICY_VERSION
from nicx.privacidade.client import AnalyticsClient
from nicx.servidor.rotas import privacidade as analytics_routes


@pytest.fixture
def app_com_escolha_antiga(tmp_path: Path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(
        "[analytics]\nenabled = true\nchoice_recorded = true\n"
        'policy_version = "2026-10-28"\n',
        encoding="utf-8",
    )
    cfg = NicxConfig()
    cfg._config_path = path
    cfg.analytics.anon_id_path = str(tmp_path / "anon_id")
    cfg.analytics.host = "https://analytics.example.invalid"
    cfg.analytics.key = "phc_test"
    cfg.analytics.enabled = True
    cfg.analytics.choice_recorded = True
    cfg.analytics.policy_version = "2026-10-28"

    def fake_sdk(client):
        client._sink = MagicMock()

    monkeypatch.setattr(AnalyticsClient, "_init_sdk", fake_sdk)
    app = FastAPI()
    app.state.config = cfg
    app.state.bus = EventBus()
    app.include_router(analytics_routes.router)
    analytics_routes.configure_analytics(app, cfg)
    yield app, path, cfg
    analytics_routes.stop_analytics(app)


def test_pergunta_de_novo_e_mantem_a_escolha_ate_responder(app_com_escolha_antiga):
    app, _path, _cfg = app_com_escolha_antiga
    corpo = TestClient(app).get("/v1/analytics/identity").json()
    assert corpo["choice_recorded"] is False
    assert corpo["policy_changed"] is True
    # Até a resposta vale o que a pessoa escolheu antes.
    assert corpo["enabled"] is True


def test_confirmar_de_novo_grava_a_versao_e_registra(app_com_escolha_antiga):
    app, path, cfg = app_com_escolha_antiga
    sdk = app.state.analytics_client._sink
    http = TestClient(app)

    corpo = http.post("/v1/analytics/preference", json={"enabled": True}).json()
    assert corpo["choice_recorded"] is True
    assert corpo["policy_changed"] is False
    assert cfg.analytics.policy_version == POLICY_VERSION
    gravado = tomllib.loads(path.read_text(encoding="utf-8"))
    assert gravado["analytics"]["policy_version"] == POLICY_VERSION

    eventos = [c.args[1] for c in sdk.capture.call_args_list]
    assert eventos == ["analytics_consent"]
    props = sdk.capture.call_args_list[0].args[2]
    assert props == {"granted": True, "policy_version": POLICY_VERSION}

    # Salvar de novo a mesma escolha não repete o registro.
    http.post("/v1/analytics/preference", json={"enabled": True})
    assert [c.args[1] for c in sdk.capture.call_args_list] == ["analytics_consent"]


def test_escolha_sem_versao_de_instalacao_antiga_pergunta_de_novo(tmp_path):
    cfg = NicxConfig()
    cfg._config_path = tmp_path / "config.toml"
    cfg.analytics.choice_recorded = True  # gravado antes de existir a versão
    app = FastAPI()
    app.state.config = cfg
    app.include_router(analytics_routes.router)
    corpo = TestClient(app).get("/v1/analytics/identity").json()
    assert corpo["choice_recorded"] is False
    assert corpo["policy_changed"] is True
    assert corpo["enabled"] is False
