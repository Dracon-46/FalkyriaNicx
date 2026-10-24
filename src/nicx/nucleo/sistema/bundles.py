"""Bundle dataclasses that group cohesive subsystems of NicxSystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from nicx.agenda.scheduler import TaskScheduler
    from nicx.agenda.store import SchedulerStore
    from nicx.cerebro.agentes._stubs import BaseAgent
    from nicx.cerebro.agentes.executor import AgentExecutor
    from nicx.cerebro.agentes.manager import AgentManager
    from nicx.cerebro.agentes.scheduler import AgentScheduler
    from nicx.registros.rastros.collector import TraceCollector
    from nicx.registros.rastros.store import TraceStore
    from nicx.registros.telemetria.gpu_monitor import GpuMonitor
    from nicx.registros.telemetria.store import TelemetryStore
    from nicx.seguranca.audit import AuditLogger
    from nicx.seguranca.boundary import BoundaryGuard
    from nicx.seguranca.capabilities import CapabilityPolicy


@dataclass
class SecurityContext:
    """Security policy, audit, and boundary enforcement."""

    capability_policy: Optional[CapabilityPolicy] = None
    audit_logger: Optional[AuditLogger] = None
    boundary_guard: Optional[BoundaryGuard] = None
    rate_limiter: Optional[Any] = None


@dataclass
class Observability:
    """Telemetry, traces, and hardware monitoring."""

    telemetry_store: Optional[TelemetryStore] = None
    trace_store: Optional[TraceStore] = None
    trace_collector: Optional[TraceCollector] = None
    gpu_monitor: Optional[GpuMonitor] = None


@dataclass
class AgentRuntime:
    """Active agent and agent lifecycle managers."""

    agent: Optional[BaseAgent] = None
    agent_name: str = ""
    manager: Optional[AgentManager] = None
    scheduler: Optional[AgentScheduler] = None
    executor: Optional[AgentExecutor] = None


@dataclass
class Scheduling:
    """Task scheduler and its persistent store."""

    store: Optional[SchedulerStore] = None
    runner: Optional[TaskScheduler] = None
