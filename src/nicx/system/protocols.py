"""Structural protocols for substituting fakes in place of NicxSystem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Protocol

if TYPE_CHECKING:
    from nicx.core.config import NicxConfig
    from nicx.core.events import EventBus
    from nicx.engine._stubs import InferenceEngine
    from nicx.security.capabilities import CapabilityPolicy
    from nicx.sessions.session import SessionStore
    from nicx.tools._stubs import BaseTool
    from nicx.tools.storage._stubs import MemoryBackend
    from nicx.traces.collector import TraceCollector
    from nicx.traces.store import TraceStore


class OrchestratorDeps(Protocol):
    """Minimum surface of NicxSystem that QueryOrchestrator depends on.

    Tests can satisfy this with a lightweight class — no need to construct
    the full NicxSystem dataclass or materialize every subsystem.
    """

    config: NicxConfig
    bus: EventBus
    engine: InferenceEngine
    engine_key: str
    model: str
    agent_name: str
    tools: List[BaseTool]
    memory_backend: Optional[MemoryBackend]
    capability_policy: Optional[CapabilityPolicy]
    rate_limiter: Optional[Any]
    session_store: Optional[SessionStore]
    trace_store: Optional[TraceStore]
    trace_collector: Optional[TraceCollector]  # written by _run_agent

    # Optional attribute (getattr with default) — declared for type clarity.
    _skill_few_shot_examples: Any
