"""PUT /v1/memory/config: as opções da memória gravam no config.toml e valem já.

Antes a página de Configurações guardava essas opções só no navegador e o
servidor nunca as lia.
"""

from __future__ import annotations

import pytest
import tomllib

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from nicx.nucleo.config import NicxConfig  # noqa: E402
from nicx.servidor.rotas.api import include_all_routes  # noqa: E402


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    caminho = tmp_path / "config.toml"
    caminho.write_text(
        '[engine]\ndefault = "ollama"\n\n[memory]\ncontext_top_k = 5\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("NICX_HOME", str(tmp_path))
    config = NicxConfig()
    config._config_path = caminho
    app = FastAPI()
    include_all_routes(app)
    app.state.config = config
    return TestClient(app), config, caminho


def test_grava_no_arquivo_e_na_config_do_servidor(cliente):
    client, config, caminho = cliente
    resp = client.put(
        "/v1/memory/config",
        json={
            "context_from_memory": False,
            "context_top_k": 8,
            "context_min_score": 0.25,
            "context_max_tokens": 1024,
        },
    )
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["context_from_memory"] is False
    assert corpo["context_top_k"] == 8
    assert corpo["context_min_score"] == 0.25
    assert corpo["context_max_tokens"] == 1024

    # Vale para o próximo pedido sem reiniciar.
    assert config.agent.context_from_memory is False
    assert config.memory.context_top_k == 8

    # E fica no arquivo, sem apagar o resto.
    gravado = tomllib.loads(caminho.read_text(encoding="utf-8"))
    assert gravado["engine"]["default"] == "ollama"
    assert gravado["agent"]["context_from_memory"] is False
    assert gravado["memory"]["context_top_k"] == 8
    assert gravado["memory"]["context_min_score"] == 0.25
    assert gravado["memory"]["context_max_tokens"] == 1024


def test_so_muda_o_que_veio(cliente):
    client, config, caminho = cliente
    resp = client.put("/v1/memory/config", json={"context_top_k": 3})
    assert resp.status_code == 200
    gravado = tomllib.loads(caminho.read_text(encoding="utf-8"))
    assert gravado["memory"] == {"context_top_k": 3}
    assert "agent" not in gravado


@pytest.mark.parametrize(
    "corpo",
    [
        {"context_top_k": 0},
        {"context_top_k": 99},
        {"context_min_score": 1.5},
        {"context_max_tokens": 100},
    ],
)
def test_recusa_valor_fora_da_faixa(cliente, corpo):
    client, _config, caminho = cliente
    antes = caminho.read_text(encoding="utf-8")
    resp = client.put("/v1/memory/config", json=corpo)
    assert resp.status_code == 422
    assert caminho.read_text(encoding="utf-8") == antes
