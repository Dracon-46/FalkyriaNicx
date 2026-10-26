"""End-to-end tests for ``nicx ask``."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from nicx.comandos import cli
from nicx.nucleo.config import NicxConfig

# Import the actual module (not the Click command attribute)
_ask_mod = importlib.import_module("nicx.comandos.ask")


def _mock_engine_response():
    """Return a mock engine that generates a fixed response."""
    return {
        "content": "The answer is 4.",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "model": "test-model",
        "finish_reason": "stop",
    }


def _patch_ask(monkeypatch, tmp_path, *, engine_result=None, no_engine=False):
    """Set up common mocks for ask tests."""
    # Re-register SimpleAgent after the autouse `_clean_registries` conftest
    # fixture clears it. ``NicxConfig().agent.default_agent`` defaults to
    # ``"simple"``, so ``nicx ask "..."`` (no --agent) routes through it.
    from nicx.cerebro.agentes.conversa.simple import SimpleAgent
    from nicx.nucleo.registry import AgentRegistry

    if not AgentRegistry.contains("simple"):
        AgentRegistry.register_value("simple", SimpleAgent)

    cfg = NicxConfig()
    cfg.telemetry.db_path = str(tmp_path / "telemetry.db")
    cfg.traces.enabled = False

    monkeypatch.setattr(_ask_mod, "load_config", lambda: cfg)

    if no_engine:
        monkeypatch.setattr(_ask_mod, "get_engine", lambda *a, **kw: None)
    else:
        fake_engine = mock.MagicMock()
        fake_engine.engine_id = "mock"
        fake_engine.health.return_value = True
        fake_engine.generate.return_value = engine_result or _mock_engine_response()
        fake_engine.list_models.return_value = ["test-model"]
        monkeypatch.setattr(
            _ask_mod,
            "get_engine",
            lambda *a, **kw: ("mock", fake_engine),
        )
        monkeypatch.setattr(
            _ask_mod,
            "discover_engines",
            lambda c: [("mock", fake_engine)],
        )
        monkeypatch.setattr(
            _ask_mod,
            "discover_models",
            lambda e: {"mock": ["test-model"]},
        )


class TestAskCommand:
    def test_basic_response(self, monkeypatch, tmp_path: Path) -> None:
        _patch_ask(monkeypatch, tmp_path)
        result = CliRunner().invoke(cli, ["ask", "What is 2+2?"])
        assert result.exit_code == 0
        assert "The answer is 4" in result.output

    def test_no_engine_error(self, monkeypatch, tmp_path: Path) -> None:
        _patch_ask(monkeypatch, tmp_path, no_engine=True)
        result = CliRunner().invoke(cli, ["ask", "Hello"])
        assert result.exit_code != 0

    def test_out_of_memory_prints_advice_not_traceback(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from nicx.motores._base import EngineOutOfMemoryError

        _patch_ask(monkeypatch, tmp_path)
        oom = EngineOutOfMemoryError(
            "O Ollama não tem memória suficiente para carregar o modelo. "
            "Reduza [engine.ollama] num_ctx.",
            status=500,
            detail="llama-server reported out-of-memory",
        )
        _ask_mod.get_engine()[1].generate.side_effect = oom
        for args in (["ask", "Oi"], ["ask", "--agent", "", "Oi"]):
            result = CliRunner().invoke(cli, args)
            assert result.exit_code == 1
            assert isinstance(result.exception, SystemExit)
            assert "Sem memória" in result.output
            # Rich must print the "[engine.ollama]" text, not eat it as markup.
            assert "[engine.ollama] num_ctx" in result.output
            assert "out-of-memory" in result.output

    def test_engine_http_error_is_reported_cleanly(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from nicx.motores._base import EngineRequestError

        _patch_ask(monkeypatch, tmp_path)
        _ask_mod.get_engine()[1].generate.side_effect = EngineRequestError(
            "Ollama returned 404: model not found", status=404
        )
        result = CliRunner().invoke(cli, ["ask", "--agent", "", "Oi"])
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "model not found" in result.output

    def test_model_override(self, monkeypatch, tmp_path: Path) -> None:
        _patch_ask(monkeypatch, tmp_path)
        result = CliRunner().invoke(cli, ["ask", "-m", "custom-model", "Hello"])
        assert result.exit_code == 0

    def test_json_output(self, monkeypatch, tmp_path: Path) -> None:
        _patch_ask(monkeypatch, tmp_path)
        result = CliRunner().invoke(cli, ["ask", "--json", "Hello"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "content" in data

    def test_telemetry_recorded(self, monkeypatch, tmp_path: Path) -> None:
        _patch_ask(monkeypatch, tmp_path)
        CliRunner().invoke(cli, ["ask", "Hello"])
        db_path = tmp_path / "telemetry.db"
        assert db_path.exists()
