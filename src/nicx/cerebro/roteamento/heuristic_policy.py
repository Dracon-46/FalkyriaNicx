"""Wire the existing HeuristicRouter into the RouterPolicyRegistry."""

from __future__ import annotations

from nicx.cerebro.roteamento.router import HeuristicRouter
from nicx.nucleo.registry import RouterPolicyRegistry


def ensure_registered() -> None:
    """Register HeuristicRouter if not already present."""
    if not RouterPolicyRegistry.contains("heuristic"):
        RouterPolicyRegistry.register_value("heuristic", HeuristicRouter)


ensure_registered()
