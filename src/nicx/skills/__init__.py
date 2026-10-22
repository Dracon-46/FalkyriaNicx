"""Skill system — reusable multi-tool compositions."""

from nicx.skills.dependency import (
    DependencyCycleError,
    DepthExceededError,
    build_dependency_graph,
    compute_capability_union,
    validate_dependencies,
)
from nicx.skills.executor import SkillExecutor, SkillResult
from nicx.skills.importer import ImportResult, SkillImporter
from nicx.skills.loader import (
    discover_skills,
    load_skill,
    load_skill_directory,
    load_skill_markdown,
)
from nicx.skills.manager import SkillManager
from nicx.skills.parser import SkillParseError, SkillParser
from nicx.skills.tool_adapter import SkillTool
from nicx.skills.tool_translator import TOOL_TRANSLATION, ToolTranslator
from nicx.skills.types import SkillManifest, SkillStep

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
