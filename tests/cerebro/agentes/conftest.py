"""Shared fixtures for agent tests."""

from __future__ import annotations

import pytest

from nicx.cerebro.agentes.executor import AgentExecutor
from nicx.cerebro.agentes.manager import AgentManager
from nicx.cerebro.agentes.scheduler import AgentScheduler
from nicx.nucleo.events import EventBus
from tests.cerebro.agentes.fake_engine import FakeEngine
from tests.cerebro.agentes.scenario_harness import FakeSystem, ScenarioHarness


@pytest.fixture
def scenario_harness(tmp_path):
    """Wire up real components for agent lifecycle testing."""
    from nicx.cerebro.agentes.monitor_operative import MonitorOperativeAgent
    from nicx.nucleo.registry import AgentRegistry

    # Re-register agent types (conftest auto-clears registries)
    if not AgentRegistry.contains("monitor_operative"):
        AgentRegistry.register("monitor_operative")(MonitorOperativeAgent)

    db_path = str(tmp_path / "agents.db")
    bus = EventBus(record_history=True)
    manager = AgentManager(db_path=db_path)

    engine = FakeEngine([{"content": "Default response."}])
    system = FakeSystem(engine=engine)

    executor = AgentExecutor(manager=manager, event_bus=bus)
    executor.set_system(system)

    scheduler = AgentScheduler(
        manager=manager,
        executor=executor,
        event_bus=bus,
    )

    return ScenarioHarness(
        manager=manager,
        executor=executor,
        scheduler=scheduler,
        bus=bus,
        engine=engine,
        system=system,
        db_path=db_path,
    )
