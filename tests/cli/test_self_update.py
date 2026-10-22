"""Smoke tests for `nicx self-update`.

Focus on the surface that's easy to corrupt (output formatting, exit
codes, --check short-circuit, refused install sources). We don't actually
run git/uv from a unit test; the subprocess call is mocked.
"""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nicx.cli._install_detect import InstallInfo
from nicx.cli.self_update_cmd import _fetch_url, self_update


def _mock_info(kind: str = "pypi") -> InstallInfo:
    return InstallInfo(
        kind=kind,
        upgrade_command={
            "pypi": "pip install --upgrade nicx",
            "uv-tool": "uv tool upgrade nicx",
            "editable-git": "nicx self-update",
            "unknown": "pip install --upgrade nicx",
        }[kind],
        repo_root=Path("/tmp/repo with spaces") if kind == "editable-git" else None,
    )


@pytest.fixture(autouse=True)
def _falkyria_remote(monkeypatch):
    """Resolve the checkout's remote without shelling out to git."""
    monkeypatch.setattr(
        "nicx.cli.self_update_cmd._fetch_url",
        lambda repo_root: "https://git.example/falkyria/nicx.git",
    )


def test_check_flag_prints_plan_and_exits_clean():
    with patch(
        "nicx.cli.self_update_cmd.detect_install",
        return_value=_mock_info("editable-git"),
    ):
        runner = CliRunner()
        result = runner.invoke(self_update, ["--check"])
    assert result.exit_code == 0
    assert "Install method: editable-git" in result.output
    assert "Remote: https://git.example/falkyria/nicx.git" in result.output
    assert "git pull --ff-only" in result.output


@pytest.mark.parametrize("kind", ["pypi", "editable-git"])
def test_check_does_not_invoke_subprocess(kind):
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info(kind),
        ),
        patch("nicx.cli.self_update_cmd.subprocess.run") as mock_run,
    ):
        CliRunner().invoke(self_update, ["--check"])
    mock_run.assert_not_called()


@pytest.mark.parametrize("kind", ["pypi", "uv-tool", "unknown"])
def test_package_index_installs_are_refused(kind):
    """The ``nicx`` name on PyPI is not Falkyria's: never install from it."""
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info(kind),
        ),
        patch("nicx.cli.self_update_cmd.subprocess.run") as mock_run,
    ):
        result = CliRunner().invoke(self_update, ["-y"])
    assert result.exit_code == 1
    assert "não pertence à Falkyria" in result.output
    mock_run.assert_not_called()


@pytest.mark.parametrize(
    ("proc", "expected"),
    [
        (
            CompletedProcess([], 0, stdout="https://git.example/n.git\n"),
            "https://git.example/n.git",
        ),
        (CompletedProcess([], 128, stdout="", stderr="fatal"), ""),
    ],
)
def test_fetch_url_asks_git_for_the_default_remote(proc, expected):
    with patch("nicx.cli.self_update_cmd.subprocess.run", return_value=proc) as run:
        assert _fetch_url(Path("/repo")) == expected
    assert run.call_args.args[0] == ["git", "ls-remote", "--get-url"]
    assert run.call_args.kwargs["cwd"] == Path("/repo")


@pytest.mark.parametrize("shallow", ["true", "false"])
def test_editable_git_repairs_history_and_rebuilds_active_venv(monkeypatch, shallow):
    """Recover tags before rebuilding even when Git has no new commits."""
    mock_proc = CompletedProcess([], 0, stdout=shallow + "\n", stderr="")
    monkeypatch.setattr("nicx.cli.self_update_cmd.sys.prefix", "/managed venv")
    monkeypatch.setattr(
        "nicx.cli.self_update_cmd.sys.executable", "/managed venv/bin/python"
    )
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info("editable-git"),
        ),
        patch(
            "nicx.cli.self_update_cmd.subprocess.run",
            return_value=mock_proc,
        ) as mock_run,
    ):
        result = CliRunner().invoke(self_update, ["-y"])
    assert result.exit_code == 0, result.output
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands[0] == ["git", "rev-parse", "--is-shallow-repository"]
    assert commands[1] == ["git", "fetch", "--tags"] + (
        ["--unshallow"] if shallow == "true" else []
    )
    assert commands[2] == ["git", "pull", "--ff-only"]
    assert commands[3] == [
        "uv",
        "sync",
        "--python",
        "/managed venv/bin/python",
        "--inexact",
        "--reinstall-package",
        "nicx",
    ]
    for call in mock_run.call_args_list:
        assert call.kwargs.get("shell") is not True
        assert call.kwargs["cwd"] == _mock_info("editable-git").repo_root
    assert mock_run.call_args.kwargs["env"]["UV_PROJECT_ENVIRONMENT"] == "/managed venv"


def test_editable_global_install_rebuilds_running_interpreter(monkeypatch):
    mock_proc = CompletedProcess([], 0, stdout="false\n", stderr="")
    monkeypatch.setattr("nicx.cli.self_update_cmd.sys.prefix", "/global python")
    monkeypatch.setattr("nicx.cli.self_update_cmd.sys.base_prefix", "/global python")
    monkeypatch.setattr(
        "nicx.cli.self_update_cmd.sys.executable", "/global python/python"
    )
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info("editable-git"),
        ),
        patch(
            "nicx.cli.self_update_cmd.subprocess.run",
            return_value=mock_proc,
        ) as mock_run,
    ):
        result = CliRunner().invoke(self_update, ["-y"])

    assert result.exit_code == 0
    assert mock_run.call_args.args[0] == [
        "uv",
        "pip",
        "install",
        "--python",
        "/global python/python",
        "--reinstall-package",
        "nicx",
        "-e",
        ".",
    ]


@pytest.mark.parametrize("failed_step", [0, 1, 2, 3])
def test_editable_upgrade_stops_on_failure(monkeypatch, failed_step):
    monkeypatch.setattr("nicx.cli.self_update_cmd.sys.prefix", "/managed venv")
    responses = [CompletedProcess([], 0, stdout="true\n", stderr="")] * failed_step
    responses.append(CompletedProcess([], 7, stdout="", stderr="failed"))
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info("editable-git"),
        ),
        patch("nicx.cli.self_update_cmd.subprocess.run", side_effect=responses) as run,
    ):
        result = CliRunner().invoke(self_update, ["-y"])
    assert result.exit_code == 7
    assert run.call_count == failed_step + 1
    assert "Upgrade complete" not in result.output


def test_decline_confirmation_exits_nonzero():
    with (
        patch(
            "nicx.cli.self_update_cmd.detect_install",
            return_value=_mock_info("editable-git"),
        ),
        patch("nicx.cli.self_update_cmd.subprocess.run") as mock_run,
    ):
        result = CliRunner().invoke(self_update, input="n\n")
    assert result.exit_code == 1
    assert "Aborted" in result.output
    mock_run.assert_not_called()
