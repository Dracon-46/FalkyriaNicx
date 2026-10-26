"""Agents primitive — multi-turn reasoning and tool use."""

from __future__ import annotations

import logging

from nicx.cerebro.agentes._stubs import (
    AgentContext,
    AgentResult,
    BaseAgent,
    ToolUsingAgent,
)

logger = logging.getLogger(__name__)

# Import agent modules to trigger @AgentRegistry.register() decorators
try:
    import nicx.cerebro.agentes.conversa.simple  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.conversa.orchestrator  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.conversa.native_react  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.conversa.codeact  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.conversa.rlm  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.autonomos.operative  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.autonomos.monitor_operative  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.pesquisa.deep_research  # noqa: F401
except ImportError:
    pass

try:
    import nicx.cerebro.agentes.autonomos.morning_digest  # noqa: F401
except ImportError:
    pass

# Registry alias: "react" -> NativeReActAgent (for backward compat)
try:
    from nicx.nucleo.registry import AgentRegistry

    if AgentRegistry.contains("native_react") and not AgentRegistry.contains("react"):
        AgentRegistry.register_value("react", AgentRegistry.get("native_react"))
except Exception as exc:
    logger.debug("Registry alias 'react' creation skipped: %s", exc)

__all__ = ["AgentContext", "AgentResult", "BaseAgent", "ToolUsingAgent"]
