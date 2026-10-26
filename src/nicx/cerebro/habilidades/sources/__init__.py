"""Origens de skills: base comum e repositórios GitHub."""

from nicx.cerebro.habilidades.sources.base import ResolvedSkill, SourceResolver
from nicx.cerebro.habilidades.sources.github import GitHubResolver

__all__ = ["GitHubResolver", "ResolvedSkill", "SourceResolver"]
