"""Learning primitive -- router policies, reward functions, learning."""

from __future__ import annotations

from nicx.learning._stubs import (
    QueryAnalyzer,
    RewardFunction,
    RouterPolicy,
    RoutingContext,
)
from nicx.learning.agents.agent_evolver import AgentConfigEvolver
from nicx.learning.learning_orchestrator import LearningOrchestrator
from nicx.learning.optimize.llm_optimizer import LLMOptimizer
from nicx.learning.optimize.optimizer import OptimizationEngine
from nicx.learning.optimize.store import OptimizationStore
from nicx.learning.routing.complexity import (
    ComplexityQueryAnalyzer,
    score_complexity,
)
from nicx.learning.routing.heuristic_reward import HeuristicRewardFunction
from nicx.learning.routing.router import (
    HeuristicRouter,
    build_routing_context,
)
from nicx.learning.training.data import TrainingDataMiner
from nicx.learning.training.lora import HAS_TORCH, LoRATrainer, LoRATrainingConfig


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

    # Intelligence training (optional deps)
    try:
        import nicx.learning.intelligence  # noqa: F401
    except ImportError:
        pass

    # Orchestrator-specific training (optional deps)
    try:
        import nicx.learning.intelligence.orchestrator  # noqa: F401
    except ImportError:
        pass

    # Agent optimizers (optional deps)
    try:
        import nicx.learning.agents.dspy_optimizer  # noqa: F401
    except ImportError:
        pass
    try:
        import nicx.learning.agents.gepa_optimizer  # noqa: F401
    except ImportError:
        pass
    try:
        import nicx.learning.agents.ace_optimizer  # noqa: F401
    except ImportError:
        pass


__all__ = [
    "AgentConfigEvolver",
    "ComplexityQueryAnalyzer",
    "HAS_TORCH",
    "HeuristicRewardFunction",
    "HeuristicRouter",
    "LLMOptimizer",
    "LearningOrchestrator",
    "LoRATrainer",
    "LoRATrainingConfig",
    "OptimizationEngine",
    "OptimizationStore",
    "QueryAnalyzer",
    "RewardFunction",
    "RouterPolicy",
    "RoutingContext",
    "TrainingDataMiner",
    "build_routing_context",
    "ensure_registered",
    "score_complexity",
]
