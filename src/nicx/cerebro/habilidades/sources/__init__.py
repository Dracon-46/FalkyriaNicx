"""Skill source resolvers — Hermes, OpenClaw, generic GitHub."""

from nicx.cerebro.habilidades.sources.base import ResolvedSkill, SourceResolver
from nicx.cerebro.habilidades.sources.github import GitHubResolver
from nicx.cerebro.habilidades.sources.hermes import HERMES_REPO_URL, HermesResolver
from nicx.cerebro.habilidades.sources.openclaw import (
    OPENCLAW_REPO_URL,
    OpenClawResolver,
)

__all__ = [
    "GitHubResolver",
    "HERMES_REPO_URL",
    "HermesResolver",
    "OPENCLAW_REPO_URL",
    "OpenClawResolver",
    "ResolvedSkill",
    "SourceResolver",
]
