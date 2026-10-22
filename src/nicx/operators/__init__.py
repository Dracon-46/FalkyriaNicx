"""Operators — persistent, scheduled autonomous agents."""

from nicx.operators.loader import load_operator
from nicx.operators.manager import OperatorManager
from nicx.operators.types import OperatorManifest

__all__ = ["OperatorManifest", "OperatorManager", "load_operator"]
