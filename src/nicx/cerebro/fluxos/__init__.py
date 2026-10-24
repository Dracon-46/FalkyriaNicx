"""Workflow engine — DAG-based multi-agent pipelines."""

from nicx.cerebro.fluxos.builder import WorkflowBuilder
from nicx.cerebro.fluxos.engine import WorkflowEngine
from nicx.cerebro.fluxos.graph import WorkflowGraph
from nicx.cerebro.fluxos.loader import load_workflow
from nicx.cerebro.fluxos.types import (
    WorkflowEdge,
    WorkflowNode,
    WorkflowResult,
    WorkflowStepResult,
)

__all__ = [
    "WorkflowBuilder",
    "WorkflowEdge",
    "WorkflowEngine",
    "WorkflowGraph",
    "WorkflowNode",
    "WorkflowResult",
    "WorkflowStepResult",
    "load_workflow",
]
