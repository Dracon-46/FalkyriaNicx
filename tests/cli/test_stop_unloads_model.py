"""`nicx stop` frees the model's RAM even when the server is force-killed."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from nicx.cli import cli


def test_stop_unloads_the_model():
    with (
        patch("nicx.cli.gui_cmd.stop_frontend", return_value=None),
        patch("nicx.cli.daemon_cmd._read_pid", return_value=4321),
        patch("nicx.cli.daemon_cmd.terminate_process") as terminate,
        patch("nicx.cli.daemon_cmd.clear_server_state"),
        patch("nicx.engine.ollama.unload_configured_model") as unload,
    ):
        result = CliRunner().invoke(cli, ["stop"])
    assert result.exit_code == 0, result.output
    terminate.assert_called_once_with(4321, grace_seconds=10.0)
    unload.assert_called_once_with()


def test_unload_configured_model_uses_config(monkeypatch):
    from nicx.core.config import NicxConfig
    from nicx.engine import ollama

    cfg = NicxConfig()
    cfg.intelligence.default_model = "qwen3.5:4b"
    cfg.engine.ollama.host = "http://ollama.test"
    monkeypatch.setattr("nicx.core.config.load_config", lambda: cfg)
    calls = []
    monkeypatch.setattr(
        ollama.OllamaEngine,
        "unload",
        lambda self, model: calls.append((self._host, model)),
    )
    ollama.unload_configured_model()
    assert calls == [("http://ollama.test", "qwen3.5:4b")]
