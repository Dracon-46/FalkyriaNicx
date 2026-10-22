"""External-framework subprocess backends (Hermes Agent, OpenClaw)."""

from nicx.evals.backends.external.hermes_agent import HermesBackend
from nicx.evals.backends.external.openclaw import OpenClawBackend

__all__ = ["HermesBackend", "OpenClawBackend"]
