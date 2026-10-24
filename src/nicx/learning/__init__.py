"""Learning primitive -- router policies, reward functions, learning."""

from __future__ import annotations

from nicx.learning._stubs import (
    QueryAnalyzer,
    RewardFunction,
    RouterPolicy,
    RoutingContext,
)
from nicx.learning.routing.complexity import (
    ComplexityQueryAnalyzer,
    score_complexity,
)
from nicx.learning.routing.heuristic_reward import HeuristicRewardFunction
from nicx.learning.routing.router import (
    HeuristicRouter,
    build_routing_context,
)


def ensure_registered() -> None:
    """Ensure all learning policies are registered in RouterPolicyRegistry."""
    from nicx.learning.routing.heuristic_policy import (
        ensure_registered as _reg_heuristic,
    )

    _reg_heuristic()

    from nicx.learning.routing.learned_router import (
        ensure_registered as _reg_learned,
    )

    _reg_learned()


__all__ = [
    "ComplexityQueryAnalyzer",
    "HeuristicRewardFunction",
    "HeuristicRouter",
    "QueryAnalyzer",
    "RewardFunction",
    "RouterPolicy",
    "RoutingContext",
    "build_routing_context",
    "ensure_registered",
    "score_complexity",
]
