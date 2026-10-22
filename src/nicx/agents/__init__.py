"""Agents primitive — multi-turn reasoning and tool use."""

from __future__ import annotations

import logging

from nicx.agents._stubs import (
    AgentContext,
    AgentResult,
    BaseAgent,
    ToolUsingAgent,
)

logger = logging.getLogger(__name__)

# Import agent modules to trigger @AgentRegistry.register() decorators
try:
    import nicx.agents.simple  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.orchestrator  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.native_react  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.native_openhands  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.react  # noqa: F401 -- backward-compat shim
except ImportError:
    pass

try:
    import nicx.agents.openhands  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.rlm  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.claude_code  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.opencode  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.operative  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.monitor  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.monitor_operative  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.deep_research  # noqa: F401
except ImportError:
    pass

try:
    import nicx.agents.morning_digest  # noqa: F401
except ImportError:
    pass

# Registry alias: "react" -> NativeReActAgent (for backward compat)
try:
    from nicx.core.registry import AgentRegistry

    if AgentRegistry.contains("native_react") and not AgentRegistry.contains("react"):
        AgentRegistry.register_value("react", AgentRegistry.get("native_react"))
except Exception as exc:
    logger.debug("Registry alias 'react' creation skipped: %s", exc)

__all__ = ["AgentContext", "AgentResult", "BaseAgent", "ToolUsingAgent"]
