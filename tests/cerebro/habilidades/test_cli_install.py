"""End-to-end CLI tests for skill install + sync against fake sources."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from nicx.comandos import cli


def _build_fake_github_cache(cache_root: Path) -> None:
    """Build a minimal fake GitHub skills cache for testing."""
    skills_root = cache_root / "skills"
    (skills_root / "research" / "research-skill").mkdir(parents=True)
    (skills_root / "research" / "research-skill" / "SKILL.md").write_text(
        textwrap.dedent("""\
            ---
            name: research-skill
            description: A research skill
            ---

            Use the Bash tool to fetch data, then Read the file.
        """)
    )
    # Fake .git so the resolver doesn't try to clone
    (cache_root / ".git").mkdir()


class TestCliInstallE2E:
    def test_install_github_skill_e2e(self, tmp_path: Path) -> None:
        """nicx skill install github:research-skill installs to target dir."""
        from nicx.cerebro.habilidades.sources.github import GitHubResolver

        cache = tmp_path / "github-cache"
        target = tmp_path / "target"
        _build_fake_github_cache(cache)

        # A GitHubResolver pointed at the fake cache
        def _make_resolver(*_args, **_kwargs):
            return GitHubResolver(cache, "https://example.invalid/skills.git")

        # Patch the helper that builds resolvers in the CLI
        with patch(
            "nicx.comandos.agentes.skill._get_resolver",
            lambda src, url="": _make_resolver(),
        ):
            # sync is a no-op: the cache is already built
            with patch.object(GitHubResolver, "sync", lambda self: None):
                # Patch the SkillImporter constructor used inside the install
                # command so it writes to our test target instead of
                # ~/.nicx/skills/.
                from nicx.cerebro.habilidades.importer import SkillImporter as _SI

                original_init = _SI.__init__

                def patched_init(self, parser, tool_translator, target_root=None):
                    original_init(
                        self,
                        parser=parser,
                        tool_translator=tool_translator,
                        target_root=target,
                    )

                with patch.object(_SI, "__init__", patched_init):
                    result = CliRunner().invoke(
                        cli, ["skill", "install", "github:research-skill"]
                    )

        assert result.exit_code == 0, result.output
        assert "Installed" in result.output

        installed = target / "github" / "research-skill" / "SKILL.md"
        assert installed.exists(), (
            f"Expected {installed} to exist; output:\n{result.output}"
        )
        body = installed.read_text()
        assert "shell_exec" in body
        assert "file_read" in body
