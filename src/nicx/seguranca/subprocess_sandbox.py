"""Subprocess sandbox — secure process execution with environment isolation."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Safe environment variables to pass through
_SAFE_ENV_VARS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "TERM",
        "SHELL",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TZ",
    }
)

# Windows system locations, none of them secret. Without SYSTEMROOT/WINDIR
# many programs (Python included) fail to start; without PATHEXT cmd.exe
# cannot resolve "python" to "python.exe"; TEMP/TMP are the temp folder.
_WINDOWS_SAFE_ENV_VARS = frozenset(
    {
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "USERNAME",
        "APPDATA",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
    }
)


def _safe_env_vars() -> frozenset[str]:
    if sys.platform == "win32":
        return _SAFE_ENV_VARS | _WINDOWS_SAFE_ENV_VARS
    return _SAFE_ENV_VARS


@dataclass(slots=True)
class SandboxResult:
    """Result of a sandboxed subprocess execution."""

    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    timed_out: bool = False
    killed: bool = False


def build_safe_env(
    passthrough: Optional[List[str]] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build a sanitized environment dict.

    Only copies safe vars from current env, plus any in passthrough list.
    Extra vars are added directly.
    """
    env: Dict[str, str] = {}
    allowed = _safe_env_vars() | frozenset(passthrough or [])
    for key in allowed:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val
    if extra:
        env.update(extra)
    return env


def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children (best effort)."""
    if sys.platform == "win32":
        # No process groups or signals here: taskkill /T walks the child tree
        # (shell=True runs the command under cmd.exe, so the tree matters).
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("Failed to kill process tree %d: %s", pid, exc)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (OSError, ProcessLookupError) as exc:
        logger.debug("Failed to terminate process %d: %s", pid, exc)
    try:
        os.kill(pid, signal.SIGKILL)
    except (OSError, ProcessLookupError) as exc:
        logger.debug("Failed to kill process %d: %s", pid, exc)


def run_sandboxed(
    command: str,
    *,
    timeout: float = 30.0,
    working_dir: Optional[str] = None,
    env_passthrough: Optional[List[str]] = None,
    env_extra: Optional[Dict[str, str]] = None,
    max_output_bytes: int = 102_400,
) -> SandboxResult:
    """Execute a command in a sandboxed subprocess.

    Features:
    - Clean environment (only safe vars passed through)
    - Timeout enforcement with process tree kill
    - Output truncation
    - New process group for clean cleanup
    """
    env = build_safe_env(passthrough=env_passthrough, extra=env_extra)
    cwd = working_dir if working_dir and os.path.isdir(working_dir) else None

    # New process group for clean cleanup. os.setsid does not exist on Windows;
    # there the child gets its own group and a hidden console instead.
    group_kwargs: dict = {}
    if sys.platform == "win32":
        group_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        group_kwargs["start_new_session"] = True

    result = SandboxResult()
    try:
        proc = subprocess.Popen(
            command,
            # This API explicitly runs caller-provided shell commands.
            shell=True,  # nosec B602
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # Console programs may print in another code page; never crash on it.
            errors="replace",
            env=env,
            cwd=cwd,
            **group_kwargs,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            result.stdout = stdout[:max_output_bytes] if stdout else ""
            result.stderr = stderr[:max_output_bytes] if stderr else ""
            result.returncode = proc.returncode
        except subprocess.TimeoutExpired:
            kill_process_tree(proc.pid)
            proc.wait(timeout=5)
            result.timed_out = True
            result.killed = True
            result.returncode = -1
            result.stdout = "(timed out)"
            result.stderr = ""
    except OSError as exc:
        result.stderr = f"Execution error: {exc}"
        result.returncode = -1

    return result


__all__ = ["SandboxResult", "build_safe_env", "kill_process_tree", "run_sandboxed"]
