"""Pedido do editor de código (extensão do VS Code): direto ao modelo.

Sem ferramentas do PC, sem ler a tela, sem ações rápidas, e o código fica
fora da memória automática.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")


def _client():
    from fastapi.testclient import TestClient

    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.app import create_app

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.is_cloud = False
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "```python\nprint('oi')\n```",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    memory = MagicMock()
    memory.list_facts.return_value = []
    app = create_app(engine, "m", config=cfg, memory_service=memory)
    return TestClient(app), engine, memory


def test_editor_vai_direto_e_fica_fora_da_memoria(monkeypatch):
    from nicx.contexto import servico as contexto
    from nicx.servidor.rotas import chat

    publicados = []
    monkeypatch.setattr(
        "nicx.memoria.publish_completed_exchange",
        lambda *a, **k: publicados.append(a),
        raising=False,
    )
    chamado = []
    monkeypatch.setattr(contexto, "preparar", lambda *a, **k: chamado.append(1))
    client, engine, memory = _client()
    corpo = {
        "model": "m",
        "editor": True,
        # "abre o arquivo" seria ação rápida / ferramenta fora do editor.
        "messages": [
            {"role": "user", "content": "corrige esse código e abre o arquivo"}
        ],
    }
    resposta = client.post("/v1/chat/completions", json=corpo)
    assert resposta.status_code == 200
    assert "print('oi')" in resposta.json()["choices"][0]["message"]["content"]
    assert not engine.generate.call_args.kwargs.get("tools")
    assert chamado == []  # não leu a tela
    memory.submit.assert_not_called()
    assert publicados == []
    assert chat._SEM_MEMORIA.get() is False  # não vaza para fora do pedido
