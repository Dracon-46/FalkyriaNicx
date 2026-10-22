"""Security gates for agents that execute outside ToolUsingAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nicx.agents.claude_code import ClaudeCodeAgent
from nicx.agents.opencode import OpenCodeAgent
from nicx.agents.openhands import OpenHandsAgent
from nicx.core.events import EventBus, EventType
from nicx.security.capabilities import CapabilityPolicy


class _RecordingLimiter:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def check(self, key: str):
        self.keys.append(key)
        return True, 0.0


@pytest.mark.parametrize(
    ("agent_cls", "agent_id", "operation"),
    [
        (ClaudeCodeAgent, "restricted-claude", "agent_run"),
        (OpenCodeAgent, "restricted-opencode", "agent_run"),
        (OpenHandsAgent, "restricted-openhands", "agent_run"),
    ],
)
def test_registered_execution_agents_fail_closed_before_side_effects(
    agent_cls, agent_id, operation
):
    policy = CapabilityPolicy(default_deny=True)
    limiter = _RecordingLimiter()
    bus = EventBus(record_history=True)
    agent = agent_cls(
        MagicMock(),
        "test-model",
        bus=bus,
        capability_policy=policy,
        rate_limiter=limiter,
        agent_id=agent_id,
    )

    result = agent.run("perform workspace changes")

    assert result.metadata["security_denied"] is True
    assert "code:execute" in result.content
    assert limiter.keys == [f"{agent_id}:{operation}"]
    denied = [
        event
        for event in bus.history
        if event.event_type == EventType.CAPABILITY_DENIED
    ]
    assert denied[-1].data["agent_id"] == agent_id
