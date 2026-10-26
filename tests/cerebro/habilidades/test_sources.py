"""Tests for SourceResolver ABC and resolver implementations."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

from nicx.cerebro.habilidades.sources.base import ResolvedSkill, SourceResolver


class _FakeResolver(SourceResolver):
    """In-memory resolver used for ABC tests."""

    name = "fake"

    def __init__(self, skills: List[ResolvedSkill]) -> None:
        self._skills = skills

    def cache_dir(self) -> Path:
        return Path("/tmp/fake-cache")

    def sync(self) -> None:
        pass

    def list_skills(self) -> List[ResolvedSkill]:
        return list(self._skills)


class TestResolvedSkill:
    def test_create(self):
        skill = ResolvedSkill(
            name="my-skill",
            source="hermes",
            path=Path("/tmp/x"),
            category="research",
            description="Does research",
            commit="abc123",
        )
        assert skill.name == "my-skill"
        assert skill.source == "hermes"

    def test_default_sidecar_data(self):
        skill = ResolvedSkill(
            name="x",
            source="x",
            path=Path("/tmp"),
            category="",
            description="",
            commit="",
        )
        assert skill.sidecar_data == {}


class TestSourceResolverABC:
    def test_resolve_filters_by_name(self):
        skills = [
            ResolvedSkill(
                name="research-it",
                source="fake",
                path=Path("/tmp/r"),
                category="research",
                description="x",
                commit="a",
            ),
            ResolvedSkill(
                name="code-it",
                source="fake",
                path=Path("/tmp/c"),
                category="coding",
                description="x",
                commit="a",
            ),
        ]
        resolver = _FakeResolver(skills)
        results = resolver.resolve("research-it")
        assert len(results) == 1
        assert results[0].name == "research-it"

    def test_resolve_filters_by_partial_name(self):
        skills = [
            ResolvedSkill(
                name="research-it",
                source="fake",
                path=Path("/tmp/r"),
                category="research",
                description="x",
                commit="a",
            ),
            ResolvedSkill(
                name="code-it",
                source="fake",
                path=Path("/tmp/c"),
                category="coding",
                description="x",
                commit="a",
            ),
        ]
        resolver = _FakeResolver(skills)
        # 'res' should match 'research-it'
        results = resolver.resolve("res")
        assert len(results) == 1

    def test_resolve_empty_query_returns_all(self):
        skills = [
            ResolvedSkill(
                name="a",
                source="fake",
                path=Path("/tmp/a"),
                category="x",
                description="x",
                commit="a",
            ),
            ResolvedSkill(
                name="b",
                source="fake",
                path=Path("/tmp/b"),
                category="x",
                description="x",
                commit="a",
            ),
        ]
        resolver = _FakeResolver(skills)
        assert len(resolver.resolve("")) == 2

    def test_filter_by_category(self):
        skills = [
            ResolvedSkill(
                name="a",
                source="fake",
                path=Path("/tmp/a"),
                category="research",
                description="x",
                commit="a",
            ),
            ResolvedSkill(
                name="b",
                source="fake",
                path=Path("/tmp/b"),
                category="coding",
                description="x",
                commit="a",
            ),
        ]
        resolver = _FakeResolver(skills)
        results = resolver.filter_by_category("research")
        assert len(results) == 1
        assert results[0].category == "research"


class TestGitHubResolver:
    def test_recursive_walk_finds_skill_md(self, tmp_path: Path):
        from nicx.cerebro.habilidades.sources.github import GitHubResolver

        # Arbitrary nested layout
        d = tmp_path / "any" / "depth" / "my-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            textwrap.dedent("""\
                ---
                name: my-skill
                description: x
                ---
                Body
            """)
        )

        resolver = GitHubResolver(cache_root=tmp_path, repo_url="https://example.com/x")
        skills = resolver.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "my-skill"

    def test_finds_lowercase_skill_md(self, tmp_path: Path):
        from nicx.cerebro.habilidades.sources.github import GitHubResolver

        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "skill.md").write_text(
            textwrap.dedent("""\
                ---
                name: my-skill
                description: x
                ---
            """)
        )

        resolver = GitHubResolver(cache_root=tmp_path, repo_url="https://example.com/x")
        skills = resolver.list_skills()
        assert len(skills) == 1
