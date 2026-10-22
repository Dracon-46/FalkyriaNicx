"""Skill source resolvers — Hermes, OpenClaw, generic GitHub."""

from nicx.skills.sources.base import ResolvedSkill, SourceResolver
from nicx.skills.sources.github import GitHubResolver
from nicx.skills.sources.hermes import HERMES_REPO_URL, HermesResolver
from nicx.skills.sources.openclaw import OPENCLAW_REPO_URL, OpenClawResolver

__all__ = [
    "GitHubResolver",
    "HERMES_REPO_URL",
    "HermesResolver",
    "OPENCLAW_REPO_URL",
    "OpenClawResolver",
    "ResolvedSkill",
    "SourceResolver",
]
