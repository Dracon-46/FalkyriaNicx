"""Perguntas faladas pedem resposta curta, sem mexer no prefixo do prompt."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nicx.cerebro.agentes._stubs import AgentResult  # noqa: E402
from nicx.servidor.app import create_app  # noqa: E402
from nicx.servidor.rotas.chat import _VOICE_HINT, _VOICE_MAX_TOKENS  # noqa: E402


def _client():
    from nicx.nucleo.config import NicxConfig

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.tools_on_demand = False
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.list_models.return_value = ["m"]
    agent = MagicMock()
    agent.agent_id = "mock"
    agent._model = "m"
    agent._max_tokens = 1024
    seen = {}

    def run(text, context=None):
        seen["input"] = text
        seen["max_tokens"] = agent._max_tokens
        return AgentResult(content="Claro.", turns=1)

    agent.run.side_effect = run
    app = create_app(engine, "m", agent=agent, config=cfg)
    return TestClient(app), agent, seen


def _ask(client, **extra):
    body = {"model": "m", "messages": [{"role": "user", "content": "me conta algo"}]}
    return client.post("/v1/chat/completions", json={**body, **extra})


def test_spoken_question_asks_for_short_answer():
    client, agent, seen = _client()
    assert _ask(client, voice=True).status_code == 200
    assert seen["input"] == "me conta algo" + _VOICE_HINT
    assert seen["max_tokens"] == _VOICE_MAX_TOKENS
    assert agent._max_tokens == 1024  # restaurado depois


def test_typed_question_is_unchanged():
    client, _, seen = _client()
    _ask(client)
    assert seen["input"] == "me conta algo"
    assert seen["max_tokens"] == 1024


def test_reply_language_follows_the_interface():
    from nicx.nucleo.idiomas import instrucao_resposta

    client, _, seen = _client()
    _ask(client, language="en", voice=True)
    assert seen["input"] == "me conta algo" + instrucao_resposta("en") + _VOICE_HINT
    assert "inglês" in instrucao_resposta("en")


def test_portuguese_interface_adds_nothing():
    client, _, seen = _client()
    _ask(client, language="pt-BR")
    assert seen["input"] == "me conta algo"
