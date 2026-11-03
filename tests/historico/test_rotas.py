"""Rotas /v1/historico e /v1/autonomia."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.acoes import notas
from nicx.servidor.rotas.historico import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("NICX_CONFIG", str(tmp_path / "config.toml"))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_lista_desfaz_e_confere(client):
    notas.add("comprar pão")
    dados = client.get("/v1/historico").json()
    assert dados["mais"] is False
    (item,) = dados["itens"]
    assert item["tipo"] == "nota" and item["desfazivel"]
    resp = client.post(
        "/v1/historico/desfazer", json={"id": item["id"], "idioma": "en"}
    ).json()
    assert resp["ok"] and resp["mensagem"].startswith("Undone:")
    assert notas.all_notes() == []
    assert client.get("/v1/historico/integridade").json()["ok"]
    assert client.get("/v1/historico?tipos=nota&busca=pao").json()["itens"][0][
        "desfeito_em"
    ]


def test_valida_filtros(client):
    assert client.get("/v1/historico?tipos=inventado").status_code == 400
    assert client.get("/v1/historico?desde=ontem").status_code == 400


def test_paginacao(client):
    for i in range(3):
        notas.add(f"nota {i}")
    primeira = client.get("/v1/historico?limite=2").json()
    assert len(primeira["itens"]) == 2 and primeira["mais"]
    resto = client.get(
        f"/v1/historico?limite=2&antes_de={primeira['itens'][-1]['id']}"
    ).json()
    assert len(resto["itens"]) == 1 and not resto["mais"]


def test_autonomia_ler_e_mudar(client, tmp_path):
    from nicx.nucleo.config import load_config

    original = load_config().autonomia.nivel
    try:
        estado = client.get("/v1/autonomia").json()
        assert estado["riscos"] == ["leitura", "leve", "moderado", "alto"]
        assert (
            client.put("/v1/autonomia", json={"nivel": "Autônomo"}).json()["nivel"]
            == "autonomo"
        )
        assert 'nivel = "autonomo"' in (tmp_path / "config.toml").read_text(
            encoding="utf-8"
        )
        assert client.put("/v1/autonomia", json={"nivel": "tudo"}).status_code == 400
    finally:
        load_config().autonomia.nivel = original
