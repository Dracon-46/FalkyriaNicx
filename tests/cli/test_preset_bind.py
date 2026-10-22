"""Preset installation must preserve safe local server defaults."""

from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from nicx.cli import cli
from nicx.core.config import load_config
from nicx.server.auth_middleware import check_bind_safety


def test_chat_simple_preset_can_serve_without_an_api_key(tmp_path: Path) -> None:
    config_dir = tmp_path / ".nicx"
    config_path = config_dir / "config.toml"
    with (
        mock.patch("nicx.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
        mock.patch("nicx.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
    ):
        result = CliRunner().invoke(
            cli,
            ["init", "--preset", "chat-simple", "--no-download", "--no-scan"],
        )

    assert result.exit_code == 0, result.output
    config = load_config(config_path)
    assert config.server.host == "127.0.0.1"
    check_bind_safety(config.server.host, api_key="")
