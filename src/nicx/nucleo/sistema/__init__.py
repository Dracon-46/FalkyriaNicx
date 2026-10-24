"""Top-level system composition: NicxSystem, SystemBuilder, and helpers."""

from nicx.nucleo.sistema.builder import SystemBuilder
from nicx.nucleo.sistema.bundles import (
    AgentRuntime,
    Observability,
    Scheduling,
    SecurityContext,
)
from nicx.nucleo.sistema.core import NicxSystem
from nicx.nucleo.sistema.orchestrator import QueryOrchestrator
from nicx.nucleo.sistema.protocols import OrchestratorDeps

__all__ = [
    "AgentRuntime",
    "NicxSystem",
    "Observability",
    "OrchestratorDeps",
    "QueryOrchestrator",
    "Scheduling",
    "SecurityContext",
    "SystemBuilder",
]
