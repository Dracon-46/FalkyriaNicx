"""Core module — registries, types, configuration, and event bus."""

from __future__ import annotations

from nicx.nucleo.registry import (
    AgentRegistry,
    EngineRegistry,
    MemoryRegistry,
    ModelRegistry,
    ToolRegistry,
)
from nicx.nucleo.types import (
    Conversation,
    Message,
    ModelSpec,
    Quantization,
    Role,
    TelemetryRecord,
    ToolCall,
    ToolResult,
)
from nicx.nucleo.utils import (
    get_python_executable,
    open_browser,
    process_alive,
    terminate_process,
)

__all__ = [
    "AgentRegistry",
    "Conversation",
    "EngineRegistry",
    "MemoryRegistry",
    "Message",
    "ModelRegistry",
    "ModelSpec",
    "Quantization",
    "Role",
    "TelemetryRecord",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "get_python_executable",
    "open_browser",
    "process_alive",
    "terminate_process",
]
