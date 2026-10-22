"""Tests for hybrid local → cloud escalation in nicx ask."""

from __future__ import annotations

import importlib
from contextlib import ExitStack
from unittest import mock

import pytest
from click.testing import CliRunner

from nicx.cli import cli
from nicx.core.config import NicxConfig
from nicx.learning.routing.complexity import score_complexity

_ask_mod = importlib.import_module("nicx.cli.ask")

CLOUD_MODEL = "claude-sonnet-5-5"
LOCAL_MODEL = "qwen3.5:4b"
HARD_QUERY = (
    "Refactor this Python code step by step: "
    "`def total(xs): return sum(x for x in xs)`. First explain why the current "
    "approach is slow, then compare two alternatives and analyze the trade-offs. "
    "1. Compute the complexity. 2. Propose a faster version? "
    "3. What tests would you add?"
)
EASY_QUERY = "Oi, tudo bem?"


def _mock_engine(name: str):
    engine = mock.MagicMock()
    engine.engine_id = name
    engine.generate.return_value = {
        "content": f"answer from {name}",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": name,
        "finish_reason": "stop",
    }
    return engine


def _config(escalation_model: str = CLOUD_MODEL) -> NicxConfig:
    cfg = NicxConfig()
    cfg.telemetry.enabled = False
    cfg.agent.default_agent = ""
    cfg.agent.context_from_memory = False
    cfg.intelligence.default_model = LOCAL_MODEL
    cfg.intelligence.escalation_model = escalation_model
    return cfg


def _ask(args, cfg, local, cloud):
    """Run ``nicx ask`` where the cloud engine exists only if ``cloud`` is set."""

    def fake_get_engine(config, engine_key=None, model=None):
        if engine_key == "cloud":
            return ("cloud", cloud) if cloud is not None else None
        return ("ollama", local)

    with ExitStack() as stack:
        get_engine = stack.enter_context(
            mock.patch.object(_ask_mod, "get_engine", side_effect=fake_get_engine)
        )
        stack.enter_context(
            mock.patch.object(_ask_mod, "load_config", return_value=cfg)
        )
        stack.enter_context(
            mock.patch.object(_ask_mod, "discover_engines", return_value={})
        )
        stack.enter_context(
            mock.patch.object(
                _ask_mod, "discover_models", return_value={"ollama": [LOCAL_MODEL]}
            )
        )
        for name in ("register_builtin_models", "merge_discovered_models"):
            stack.enter_context(mock.patch.object(_ask_mod, name))
        stack.enter_context(mock.patch.object(_ask_mod, "TelemetryStore"))
        result = CliRunner().invoke(cli, ["ask", *args])
    return result, get_engine


def test_queries_are_on_the_expected_sides_of_the_threshold():
    threshold = NicxConfig().intelligence.escalation_threshold
    assert score_complexity(HARD_QUERY).score >= threshold
    assert score_complexity(EASY_QUERY).score < threshold


def test_hard_query_escalates_to_cloud_model():
    local, cloud = _mock_engine("ollama"), _mock_engine("cloud")
    result, get_engine = _ask([HARD_QUERY], _config(), local, cloud)
    assert result.exit_code == 0, result.output
    assert cloud.generate.call_args.kwargs["model"] == CLOUD_MODEL
    local.generate.assert_not_called()
    get_engine.assert_called_once_with(mock.ANY, "cloud", model=CLOUD_MODEL)
    assert f"usando {CLOUD_MODEL} na nuvem" in result.output


def test_easy_query_stays_local():
    local, cloud = _mock_engine("ollama"), _mock_engine("cloud")
    result, get_engine = _ask([EASY_QUERY], _config(), local, cloud)
    assert result.exit_code == 0, result.output
    assert local.generate.call_args.kwargs["model"] == LOCAL_MODEL
    cloud.generate.assert_not_called()
    assert all(c.args[1] != "cloud" for c in get_engine.call_args_list)


def test_missing_cloud_key_falls_back_to_local_with_notice():
    local = _mock_engine("ollama")
    result, _ = _ask([HARD_QUERY], _config(), local, cloud=None)
    assert result.exit_code == 0, result.output
    assert local.generate.call_args.kwargs["model"] == LOCAL_MODEL
    assert "Seguindo no modelo local" in result.output


def test_escalation_is_off_by_default():
    local, cloud = _mock_engine("ollama"), _mock_engine("cloud")
    result, _ = _ask([HARD_QUERY], _config(escalation_model=""), local, cloud)
    assert result.exit_code == 0, result.output
    assert local.generate.call_args.kwargs["model"] == LOCAL_MODEL
    cloud.generate.assert_not_called()


@pytest.mark.parametrize(
    "flags", [["-m", "llama3.2:3b"], ["-e", "ollama"]], ids=["model", "engine"]
)
def test_explicit_flags_win_over_escalation(flags):
    local, cloud = _mock_engine("ollama"), _mock_engine("cloud")
    result, _ = _ask([*flags, HARD_QUERY], _config(), local, cloud)
    assert result.exit_code == 0, result.output
    local.generate.assert_called_once()
    cloud.generate.assert_not_called()


def test_images_never_escalate(tmp_path):
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    local, cloud = _mock_engine("ollama"), _mock_engine("cloud")
    result, _ = _ask(["-i", str(image), HARD_QUERY], _config(), local, cloud)
    assert result.exit_code == 0, result.output
    local.generate.assert_called_once()
    cloud.generate.assert_not_called()
