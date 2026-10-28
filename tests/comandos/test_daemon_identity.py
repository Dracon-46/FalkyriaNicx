"""Daemon registrations survive clock changes without accepting recycled PIDs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from nicx.comandos.sistema import daemon as daemon_cmd


@pytest.fixture
def linux_process(tmp_path, monkeypatch):
    """Provide deterministic procfs data while using real registration files."""
    monkeypatch.setattr(daemon_cmd, "_PID_FILE", tmp_path / "server.pid")
    monkeypatch.setattr(daemon_cmd, "_STATE_FILE", tmp_path / "server.json")
    monkeypatch.setattr(daemon_cmd, "DEFAULT_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(daemon_cmd.sys, "platform", "linux")
    monkeypatch.setattr(daemon_cmd, "_pid_alive", lambda pid: True)
    process = {
        "boot_id": "70ec59ac-d41e-48ea-81a4-673a7d1f996b",
        "starts": {4321: 10000, 9876: 20000},
        "argv": ["/usr/bin/python3", "-m", "nicx.comandos", "serve"],
        "readable": True,
    }
    read_text = Path.read_text
    read_bytes = Path.read_bytes

    def proc_text(path, *args, **kwargs):
        if path.as_posix().startswith("/proc/"):
            if not process["readable"]:
                raise PermissionError("procfs unavailable")
            if path.as_posix() == "/proc/sys/kernel/random/boot_id":
                return process["boot_id"] + "\n"
            if path.name == "stat" and path.parent.name.isdecimal():
                pid = int(path.parent.name)
                # Fields 4..21 follow state; field 22 is the start tick count.
                fields = ["S", *(["0"] * 18), str(process["starts"][pid])]
                return f"{pid} (python (worker)) " + " ".join(fields)
            raise AssertionError(f"Unexpected wall-clock procfs read: {path}")
        return read_text(path, *args, **kwargs)

    def proc_bytes(path, *args, **kwargs):
        if path.as_posix().startswith("/proc/"):
            if not process["readable"]:
                raise PermissionError("procfs unavailable")
            assert path.name == "cmdline"
            return b"\0".join(os.fsencode(arg) for arg in process["argv"]) + b"\0"
        return read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", proc_text)
    monkeypatch.setattr(Path, "read_bytes", proc_bytes)
    return process


@pytest.mark.parametrize("mtime", [1, 1700000100.5, 2000000000])
def test_clock_adjustment_does_not_discard_registered_daemon(linux_process, mtime):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    identity = daemon_cmd._read_pid_identity()
    assert identity == {
        "pid": 4321,
        "boot_id": linux_process["boot_id"],
        "start_ticks": 10000,
    }

    os.utime(daemon_cmd._PID_FILE, (mtime, mtime))

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._bound_address() == ("127.0.0.1", 8899)
    assert daemon_cmd._read_pid_identity() == identity


def test_recycled_pid_is_never_signaled(linux_process, monkeypatch):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    # A one-tick difference is enough, even in the same wall-clock second.
    linux_process["starts"][4321] += 1
    terminate = Mock()
    monkeypatch.setattr(daemon_cmd, "terminate_process", terminate)

    result = CliRunner().invoke(daemon_cmd.stop)

    assert result.exit_code == 1
    assert "No running server" in result.output
    terminate.assert_not_called()
    assert not daemon_cmd._PID_FILE.exists()
    assert not daemon_cmd._STATE_FILE.exists()
    assert daemon_cmd._read_pid_identity() == {}
    daemon_cmd._write_pid(9876, "127.0.0.1", 8900)
    assert daemon_cmd._read_pid() == 9876


def test_reboot_rejects_even_an_identical_pid_and_start_tick(linux_process):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    linux_process["boot_id"] = "f7a07684-5a47-475b-b3da-0f507296996a"

    assert daemon_cmd._read_pid() is None
    assert not daemon_cmd._PID_FILE.exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["/venv/bin/nicx", "serve"],
        ["/venv/bin/nicx", "--quiet", "serve"],
        ["/venv/bin/nicx", "--verbose", "--pick-model", "--", "serve"],
        ["/venv/bin/python3", "/venv/bin/nicx", "--quiet", "serve"],
        ["/venv/bin/python3", "-u", "/venv/bin/nicx", "serve"],
        ["/venv/bin/python3", "-uO", "-Wignore", "-Xdev", "/venv/bin/nicx", "serve"],
        ["/venv/bin/python3", "--", "/venv/bin/nicx", "serve"],
        ["/venv/bin/python3", "-u", "-m", "nicx.comandos", "serve"],
        ["/venv/bin/python3", "-mnicx.comandos", "serve"],
        ["/venv/bin/python3", "-W", "", "-m", "nicx.comandos", "serve"],
        [
            "/venv/bin/python3",
            "-W",
            "ignore",
            "-X",
            "dev",
            "-m",
            "nicx.comandos",
            "serve",
        ],
    ],
)
def test_live_legacy_daemon_is_migrated_without_wall_clock(linux_process, argv):
    daemon_cmd._PID_FILE.write_text("4321")
    os.utime(daemon_cmd._PID_FILE, (1, 1))
    linux_process["argv"] = argv

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._read_pid_identity()["start_ticks"] == 10000
    linux_process["starts"][4321] += 1
    assert daemon_cmd._read_pid() is None


@pytest.mark.parametrize(
    "argv",
    [
        ["/usr/bin/python3", "-c", "import time; time.sleep(30)"],
        ["/usr/bin/python3", "/tmp/worker.py", "-m", "nicx.comandos", "serve"],
        ["/usr/bin/python3", "-u", "/tmp/worker.py", "-m", "nicx.comandos", "serve"],
        ["/usr/bin/python3", "-c", "pass", "-m", "nicx.comandos", "serve"],
        ["/usr/bin/python3", "--", "-m", "nicx.comandos", "serve"],
        ["/usr/bin/python3", "-W", "-m", "nicx.comandos", "serve"],
        [
            "/usr/bin/python3",
            "-W",
            "",
            "/tmp/worker.py",
            "-m",
            "nicx.comandos",
            "serve",
        ],
        ["/usr/bin/not-python", "-m", "nicx.comandos", "serve"],
        ["/venv/bin/nicx", "ask", "serve"],
        ["/venv/bin/nicx", "--help", "serve"],
        ["/usr/bin/python3", "-m", "other", "-m", "nicx.comandos", "serve"],
    ],
)
def test_legacy_unrelated_process_is_not_adopted_or_signaled(
    linux_process, monkeypatch, argv
):
    daemon_cmd._PID_FILE.write_text("4321")
    linux_process["argv"] = argv
    terminate = Mock()
    monkeypatch.setattr(daemon_cmd, "terminate_process", terminate)

    result = CliRunner().invoke(daemon_cmd.stop)

    assert result.exit_code == 1
    terminate.assert_not_called()
    assert not daemon_cmd._PID_FILE.exists()


@pytest.mark.parametrize("legacy", [False, True])
def test_unavailable_procfs_does_not_orphan_a_live_daemon(linux_process, legacy):
    if legacy:
        daemon_cmd._PID_FILE.write_text("4321")
    else:
        daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    identity = daemon_cmd._read_pid_identity()
    linux_process["readable"] = False

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._read_pid_identity() == identity


def test_legacy_migration_rechecks_identity_after_reading_command(
    linux_process, monkeypatch
):
    daemon_cmd._PID_FILE.write_text("4321")
    read_bytes = Path.read_bytes

    def recycled_after_read(path, *args, **kwargs):
        result = read_bytes(path, *args, **kwargs)
        if path.as_posix() == "/proc/4321/cmdline":
            linux_process["starts"][4321] += 1
        return result

    monkeypatch.setattr(Path, "read_bytes", recycled_after_read)

    assert daemon_cmd._read_pid() is None
    assert daemon_cmd._read_pid_identity() == {}


def test_legacy_migration_write_failure_keeps_verified_daemon(
    linux_process, monkeypatch
):
    daemon_cmd._PID_FILE.write_text("4321")
    daemon_cmd._STATE_FILE.write_text(
        json.dumps({"pid": 4321, "host": "127.0.0.1", "port": 8899})
    )
    monkeypatch.setattr(
        daemon_cmd,
        "secure_write_json",
        Mock(side_effect=PermissionError("state directory is read-only")),
    )
    terminate = Mock()
    monkeypatch.setattr(daemon_cmd, "terminate_process", terminate)

    status = CliRunner().invoke(daemon_cmd.status)
    assert status.exit_code == 0, status.output
    assert "Server is running" in status.output
    assert daemon_cmd._PID_FILE.read_text() == "4321"
    assert daemon_cmd._read_pid_identity() == {}
    terminate.assert_not_called()

    stopped = CliRunner().invoke(daemon_cmd.stop)
    assert stopped.exit_code == 0, stopped.output
    terminate.assert_called_once_with(4321, grace_seconds=10.0)
    assert not daemon_cmd._PID_FILE.exists()


def test_child_promotion_preserves_the_child_identity(linux_process):
    daemon_cmd._write_pid(4321, "127.0.0.1", 0, ready=False, launch_token="launch-a")
    daemon_cmd._write_pid(9876, "127.0.0.1", 8899, launch_token="launch-a")
    daemon_cmd._write_pid(4321, "127.0.0.1", 0, ready=False, launch_token="launch-a")

    assert daemon_cmd._read_pid() == 9876
    assert daemon_cmd._read_pid_identity()["start_ticks"] == 20000
    assert daemon_cmd._bound_address() == ("127.0.0.1", 8899)
    daemon_cmd.clear_server_state(4321)
    assert daemon_cmd._read_pid_identity()["pid"] == 9876


def test_macos_legacy_liveness_is_unchanged(linux_process, monkeypatch):
    # The mocked lock must still use this test host's filesystem locking API.
    monkeypatch.setattr(daemon_cmd.sys, "platform", "darwin")
    linux_process["readable"] = False
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._read_pid_identity() == {}


@pytest.fixture
def windows_process(tmp_path, monkeypatch):
    """Simulate Windows process data (creation time and command line)."""
    monkeypatch.setattr(daemon_cmd, "_PID_FILE", tmp_path / "server.pid")
    monkeypatch.setattr(daemon_cmd, "_STATE_FILE", tmp_path / "server.json")
    monkeypatch.setattr(daemon_cmd, "DEFAULT_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(daemon_cmd.sys, "platform", "win32")
    monkeypatch.setattr(daemon_cmd, "_pid_alive", lambda pid: True)
    process = {
        "created": {4321: 1761650000.25, 9876: 1761650100.5},
        "argv": [r"C:\nicx\.venv\Scripts\python.exe", "-m", "nicx.comandos", "serve"],
        "readable": True,
    }

    def identity(pid):
        if not process["readable"]:
            return None
        return {"pid": pid, "created_at": process["created"][pid]}

    def argv(pid):
        return list(process["argv"]) if process["readable"] else None

    monkeypatch.setattr(daemon_cmd, "_windows_process_identity", identity)
    monkeypatch.setattr(daemon_cmd, "_process_argv", argv)
    return process


def test_windows_registration_records_creation_time(windows_process):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)

    assert daemon_cmd._read_pid_identity() == {
        "pid": 4321,
        "created_at": 1761650000.25,
    }
    os.utime(daemon_cmd._PID_FILE, (1, 1))
    assert daemon_cmd._read_pid() == 4321


def test_windows_recycled_pid_is_never_terminated(windows_process, monkeypatch):
    # After a crash or reboot Windows quickly hands the same PID to another
    # program; `nicx stop` must not run taskkill /T on that process tree.
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    windows_process["created"][4321] += 3600
    terminate = Mock()
    monkeypatch.setattr(daemon_cmd, "terminate_process", terminate)

    result = CliRunner().invoke(daemon_cmd.stop)

    assert result.exit_code == 1
    assert "No running server" in result.output
    terminate.assert_not_called()
    assert not daemon_cmd._PID_FILE.exists()
    assert daemon_cmd._read_pid_identity() == {}


def test_windows_recycled_pid_does_not_block_start(windows_process):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    windows_process["created"][4321] += 1

    daemon_cmd._write_pid(9876, "127.0.0.1", 8900)

    assert daemon_cmd._read_pid() == 9876
    assert daemon_cmd._read_pid_identity()["created_at"] == 1761650100.5


@pytest.mark.parametrize(
    "argv",
    [
        [r"C:\nicx\.venv\Scripts\python.exe", "-m", "nicx.comandos", "serve"],
        [r"C:\nicx\.venv\Scripts\nicx.exe", "serve"],
    ],
)
def test_windows_legacy_daemon_is_migrated(windows_process, argv):
    daemon_cmd._PID_FILE.write_text("4321", encoding="utf-8")
    windows_process["argv"] = argv

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._read_pid_identity()["created_at"] == 1761650000.25


def test_windows_legacy_unrelated_process_is_not_adopted(windows_process, monkeypatch):
    daemon_cmd._PID_FILE.write_text("4321", encoding="utf-8")
    windows_process["argv"] = [r"C:\Windows\System32\notepad.exe"]
    terminate = Mock()
    monkeypatch.setattr(daemon_cmd, "terminate_process", terminate)

    result = CliRunner().invoke(daemon_cmd.stop)

    assert result.exit_code == 1
    terminate.assert_not_called()
    assert not daemon_cmd._PID_FILE.exists()


def test_windows_uninspectable_process_keeps_registration(windows_process):
    daemon_cmd._write_pid(4321, "127.0.0.1", 8899)
    identity = daemon_cmd._read_pid_identity()
    windows_process["readable"] = False

    assert daemon_cmd._read_pid() == 4321
    assert daemon_cmd._read_pid_identity() == identity


@pytest.mark.skipif(sys.platform != "win32", reason="lê um processo real do Windows")
def test_windows_identity_of_current_process_is_stable():
    first = daemon_cmd._windows_process_identity(os.getpid())

    assert first is not None
    assert first["pid"] == os.getpid()
    assert daemon_cmd._windows_process_identity(os.getpid()) == first


@pytest.mark.parametrize(
    "identity", [[], {"pid": True}, {"pid": 4321, "boot_id": "boot", "start_ticks": -1}]
)
def test_corrupt_identity_uses_legacy_verification(linux_process, identity):
    daemon_cmd._PID_FILE.write_text("4321")
    daemon_cmd._PID_FILE.with_suffix(".identity.json").write_text(json.dumps(identity))
    linux_process["argv"] = ["/usr/bin/sleep", "100"]

    assert daemon_cmd._read_pid() is None
