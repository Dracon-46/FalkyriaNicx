"""Operators — persistent, scheduled autonomous agents."""

from nicx.cerebro.operadores.loader import load_operator
from nicx.cerebro.operadores.manager import OperatorManager
from nicx.cerebro.operadores.types import OperatorManifest

__all__ = ["OperatorManifest", "OperatorManager", "load_operator"]
