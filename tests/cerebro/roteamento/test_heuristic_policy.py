"""Tests for heuristic policy registration."""

from __future__ import annotations

from nicx.cerebro.roteamento.heuristic_policy import ensure_registered
from nicx.cerebro.roteamento.router import HeuristicRouter
from nicx.nucleo.registry import RouterPolicyRegistry


class TestHeuristicPolicy:
    def test_registered_as_heuristic(self) -> None:
        ensure_registered()
        assert RouterPolicyRegistry.contains("heuristic")

    def test_value_is_heuristic_router(self) -> None:
        ensure_registered()
        assert RouterPolicyRegistry.get("heuristic") is HeuristicRouter

    def test_can_instantiate(self) -> None:
        ensure_registered()
        cls = RouterPolicyRegistry.get("heuristic")
        router = cls(available_models=["model-a"])
        assert router.available_models == ["model-a"]
