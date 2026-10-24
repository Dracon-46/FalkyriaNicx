"""Skill system — reusable multi-tool compositions."""

from nicx.cerebro.habilidades.dependency import (
    DependencyCycleError,
    DepthExceededError,
    build_dependency_graph,
    compute_capability_union,
    validate_dependencies,
)
from nicx.cerebro.habilidades.executor import SkillExecutor, SkillResult
from nicx.cerebro.habilidades.importer import ImportResult, SkillImporter
from nicx.cerebro.habilidades.loader import (
    discover_skills,
    load_skill,
    load_skill_directory,
    load_skill_markdown,
)
from nicx.cerebro.habilidades.manager import SkillManager
from nicx.cerebro.habilidades.parser import SkillParseError, SkillParser
from nicx.cerebro.habilidades.tool_adapter import SkillTool
from nicx.cerebro.habilidades.tool_translator import TOOL_TRANSLATION, ToolTranslator
from nicx.cerebro.habilidades.types import SkillManifest, SkillStep

__all__ = [
    "DependencyCycleError",
    "DepthExceededError",
    "ImportResult",
    "SkillExecutor",
    "SkillImporter",
    "SkillManager",
    "SkillManifest",
    "SkillParseError",
    "SkillParser",
    "SkillResult",
    "SkillStep",
    "SkillTool",
    "TOOL_TRANSLATION",
    "ToolTranslator",
    "build_dependency_graph",
    "compute_capability_union",
    "discover_skills",
    "load_skill",
    "load_skill_directory",
    "load_skill_markdown",
    "validate_dependencies",
]
