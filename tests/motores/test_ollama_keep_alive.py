"""Ollama keeps the model loaded between questions and frees it on exit."""

from __future__ import annotations

import json

import httpx

from nicx.motores import ollama
from nicx.motores.ollama import OllamaEngine
from nicx.nucleo.types import Message, Role


def _engine(requests: list[dict]) -> OllamaEngine:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append({"path": request.url.path, **json.loads(request.content)})
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "oi"}, "done": True},
        )

    engine = OllamaEngine(host="http://ollama.test")
    engine._client = httpx.Client(
        base_url="http://ollama.test", transport=httpx.MockTransport(handler)
    )
    return engine


def test_generate_sends_keep_alive(monkeypatch):
    monkeypatch.delenv("NICX_KEEP_ALIVE", raising=False)
    monkeypatch.setattr(ollama, "_keep_alive", lambda: "20m")
    sent: list[dict] = []
    _engine(sent).generate([Message(role=Role.USER, content="oi")], model="m")
    assert sent[0]["keep_alive"] == "20m"


def test_keep_alive_env_wins(monkeypatch):
    monkeypatch.setenv("NICX_KEEP_ALIVE", "1h")
    assert ollama._keep_alive() == "1h"


def test_keep_alive_default(monkeypatch):
    monkeypatch.delenv("NICX_KEEP_ALIVE", raising=False)

    def broken():
        raise RuntimeError("sem config")

    monkeypatch.setattr("nicx.nucleo.config.load_config", broken)
    assert ollama._keep_alive() == "20m"


def test_unload_frees_the_model():
    sent: list[dict] = []
    _engine(sent).unload("qwen3.5:4b")
    assert sent == [{"path": "/api/generate", "model": "qwen3.5:4b", "keep_alive": 0}]


def test_unload_never_raises():
    engine = OllamaEngine(host="http://127.0.0.1:9")  # nada escutando
    engine.unload("m")
