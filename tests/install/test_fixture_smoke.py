"""Smoke test that the tmp_nicx_home fixture works."""

from __future__ import annotations

from pathlib import Path

from nicx.nucleo import config as config_mod


def test_fixture_redirects_default_config_dir(tmp_nicx_home: Path) -> None:
    assert config_mod.DEFAULT_CONFIG_DIR == tmp_nicx_home
    assert tmp_nicx_home.exists()
    assert (tmp_nicx_home / ".state").exists()
    assert (tmp_nicx_home / ".state" / "models").exists()


def test_fixture_redirects_config_path(tmp_nicx_home: Path) -> None:
    assert config_mod.DEFAULT_CONFIG_PATH == tmp_nicx_home / "config.toml"
