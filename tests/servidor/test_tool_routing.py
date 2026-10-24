"""Conversa comum vai direto ao modelo; pedidos com ferramenta vão ao agente."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nicx.acoes.roteamento import conversation_needs_tools, needs_tools  # noqa: E402
from nicx.cerebro.agentes._stubs import AgentResult  # noqa: E402
from nicx.servidor.app import create_app  # noqa: E402


@pytest.mark.parametrize(
    "text",
    ["E aí, tudo bem?", "Qual é a capital da Austrália?", "Quem é você?", "Falkyria"],
)
def test_small_talk_needs_no_tools(text):
    assert not needs_tools(text)


@pytest.mark.parametrize(
    "text",
    [
        "Qual o clima de hoje?",
        "Pesquisa o preço do dólar",
        "Quanto é 27 vezes 43?",
        "lê o arquivo notas.txt",
        "aumenta o volume do pc",
        "quem ganhou o jogo ontem?",
    ],
)
def test_tool_requests_need_tools(text):
    assert needs_tools(text)


def test_short_answer_continues_a_tool_request():
    assert conversation_needs_tools(["Qual o clima de hoje?", "Sorocaba"])
    assert not conversation_needs_tools(["oi", "tudo bem?", "Sorocaba"])


def _client(tools_on_demand=True):
    from nicx.nucleo.config import NicxConfig

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.tools_on_demand = tools_on_demand
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "direto",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "model": "m",
        "finish_reason": "stop",
    }
    agent = MagicMock()
    agent.agent_id = "orchestrator"
    agent._model = "m"
    agent._max_tokens = 1024
    agent._tools = [object()]
    agent.run.return_value = AgentResult(content="agente", turns=1)
    return TestClient(create_app(engine, "m", agent=agent, config=cfg))


def _answer(client, *texts):
    messages = [{"role": "user", "content": t} for t in texts]
    resp = client.post(
        "/v1/chat/completions", json={"model": "m", "messages": messages}
    )
    return resp.json()["choices"][0]["message"]["content"]


def test_small_talk_skips_the_agent():
    assert _answer(_client(), "E aí, tudo bem?") == "direto"


def test_tool_request_uses_the_agent():
    assert _answer(_client(), "Pesquisa o preço do dólar") == "agente"


def test_follow_up_keeps_the_agent():
    assert _answer(_client(), "Qual o clima de hoje?", "Sorocaba") == "agente"


def test_routing_can_be_turned_off():
    assert _answer(_client(tools_on_demand=False), "E aí, tudo bem?") == "agente"


def test_spoken_small_talk_gets_the_voice_hint_on_the_direct_path():
    from nicx.servidor.routes import _VOICE_HINT, _VOICE_MAX_TOKENS

    client = _client()
    engine = client.app.state.engine
    client.post(
        "/v1/chat/completions",
        json={
            "model": "m",
            "messages": [{"role": "user", "content": "E aí, tudo bem?"}],
            "voice": True,
            "max_tokens": 1024,
        },
    )
    messages = engine.generate.call_args.args[0]
    assert messages[-1].content == "E aí, tudo bem?" + _VOICE_HINT
    assert engine.generate.call_args.kwargs["max_tokens"] == _VOICE_MAX_TOKENS
