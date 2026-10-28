"""Tests for per-invocation persona scope (_resolve_persona)."""

from pathlib import Path

import pytest

from nicx.cerebro.prompt.builder import SystemPromptBuilder
from nicx.nucleo.config import MemoryFilesConfig
from nicx.nucleo.paths import get_config_dir


def test_empty_persona_passes_through_global_defaults():
    mf = MemoryFilesConfig()
    out = SystemPromptBuilder._resolve_persona(mf)
    assert out.soul_path == mf.soul_path  # unchanged = backward compatible


def test_none_persona_disables_all_files():
    out = SystemPromptBuilder._resolve_persona(MemoryFilesConfig(persona_name="none"))
    assert out.soul_path == "" and out.memory_path == "" and out.user_path == ""


def test_named_persona_resolves_to_personas_dir():
    out = SystemPromptBuilder._resolve_persona(MemoryFilesConfig(persona_name="coder"))
    # Compara como Path: no Windows o separador é a barra invertida.
    base = get_config_dir() / "personas" / "coder"
    assert Path(out.soul_path) == base / "SOUL.md"
    assert Path(out.memory_path) == base / "MEMORY.md"
    assert Path(out.user_path) == base / "USER.md"


@pytest.mark.parametrize(
    "bad", ["../etc", "a/b", "..\\win", "/abs", "x/../y", "D:", "C:evil"]
)
def test_path_traversal_rejected(bad):
    with pytest.raises(ValueError):
        SystemPromptBuilder._resolve_persona(MemoryFilesConfig(persona_name=bad))


def test_none_persona_build_does_not_raise(tmp_path, monkeypatch):
    """Regression: `--persona none` resolves to empty file paths; building
    the prompt must not raise IsADirectoryError when those empty paths are read
    (Path("") is "." — reading a directory raised before the empty-path guard).
    """
    import dataclasses

    from nicx.nucleo.config import load_config

    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    cfg = load_config(tmp_path / "missing-config.toml")
    mf = dataclasses.replace(cfg.memory_files, persona_name="none")
    builder = SystemPromptBuilder(
        agent_template=cfg.agent.default_system_prompt or "",
        memory_files_config=mf,
        system_prompt_config=cfg.system_prompt,
    )
    out = builder.build()
    assert isinstance(out, str)
