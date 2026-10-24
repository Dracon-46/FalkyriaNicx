"""Comandos diretos respondem na hora, sem chamar o modelo."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nicx.acoes import Outcome  # noqa: E402
from nicx.server.app import create_app  # noqa: E402


def _config(quick_actions=True):
    from nicx.core.config import NicxConfig

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.quick_actions = quick_actions
    return cfg


@pytest.fixture
def ran(monkeypatch):
    calls: list[str] = []

    def fake_handle(text):
        calls.append(text)
        return Outcome(True, "Aumentei o volume.") if "volume" in text else None

    monkeypatch.setattr("nicx.acoes.handle", fake_handle)
    return calls


def _client(quick_actions=True):
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "resposta do modelo",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    app = create_app(engine, "m", config=_config(quick_actions))
    return TestClient(app), engine


def _body(text, **extra):
    return {"model": "m", "messages": [{"role": "user", "content": text}], **extra}


def test_command_skips_the_model(ran):
    client, engine = _client()
    resp = client.post("/v1/chat/completions", json=_body("aumenta o volume"))
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "Aumentei o volume."
    engine.generate.assert_not_called()
    assert ran == ["aumenta o volume"]


def test_command_streams_like_a_model_reply(ran):
    client, _ = _client()
    resp = client.post(
        "/v1/chat/completions", json=_body("aumenta o volume", stream=True)
    )
    events = [line[6:] for line in resp.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    text = "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks)
    assert text == "Aumentei o volume."
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_questions_still_go_to_the_model(ran):
    client, engine = _client()
    resp = client.post(
        "/v1/chat/completions", json=_body("qual a capital da Austrália?")
    )
    assert resp.json()["choices"][0]["message"]["content"] == "resposta do modelo"
    engine.generate.assert_called_once()


def test_can_be_turned_off(ran):
    client, engine = _client(quick_actions=False)
    client.post("/v1/chat/completions", json=_body("aumenta o volume"))
    engine.generate.assert_called_once()
    assert ran == []


def test_caller_tools_bypass_commands(ran):
    client, engine = _client()
    tool = {"type": "function", "function": {"name": "f", "parameters": {}}}
    client.post("/v1/chat/completions", json=_body("aumenta o volume", tools=[tool]))
    assert ran == []
