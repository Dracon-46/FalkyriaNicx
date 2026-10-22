"""Workflow engine — DAG-based multi-agent pipelines."""

from nicx.workflow.builder import WorkflowBuilder
from nicx.workflow.engine import WorkflowEngine
from nicx.workflow.graph import WorkflowGraph
from nicx.workflow.loader import load_workflow
from nicx.workflow.types import (
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
