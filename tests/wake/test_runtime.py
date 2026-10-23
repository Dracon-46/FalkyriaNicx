"""Lado de sistema do "Nicx, ligar": config.toml, estado da escuta, atalho."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from nicx.wake import runtime as rt


def test_set_wake_enabled_keeps_the_rest_of_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "# minhas notas\n"
        '[engine]\ndefault = "ollama"\n\n'
        '[speech]\nvoice_id = "pf_dora"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("NICX_CONFIG", str(config))

    rt.set_wake_enabled(True)
    text = config.read_text(encoding="utf-8")
    assert "# minhas notas" in text
    assert 'voice_id = "pf_dora"' in text
    assert "wake_word = true" in text

    rt.set_wake_enabled(False)
    assert "wake_word = false" in config.read_text(encoding="utf-8")


def test_set_wake_enabled_creates_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "novo" / "config.toml"
    monkeypatch.setenv("NICX_CONFIG", str(config))
    rt.set_wake_enabled(True)
    assert "[speech]" in config.read_text(encoding="utf-8")


def test_state_file_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "STATE_FILE", tmp_path / "wake.json")
    monkeypatch.setattr(rt, "_is_listener", lambda pid: pid == os.getpid())

    assert rt.read_state() is None
    rt.write_state("escutando", phrases=["Nicx, ligar"])
    state = rt.read_state()
    assert state is not None
    assert state["pid"] == os.getpid()
    assert state["state"] == "escutando"
    rt.clear_state()
    assert rt.read_state() is None


def test_state_of_dead_or_foreign_process_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "wake.json"
    monkeypatch.setattr(rt, "STATE_FILE", state_file)
    state_file.write_text(
        json.dumps({"pid": os.getpid(), "state": "escutando"}), encoding="utf-8"
    )
    # O PID existe, mas não é uma escuta do Nicx (PID reaproveitado).
    monkeypatch.setattr(rt, "_is_listener", lambda pid: False)
    assert rt.read_state() is None
    state_file.write_text("{ quebrado", encoding="utf-8")
    assert rt.read_state() is None


def test_autostart_shortcut(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "startup_dir", lambda: tmp_path / "Startup")
    scripts: list[str] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        scripts.append(cmd[-1])
        (tmp_path / "Startup" / rt.SHORTCUT_NAME).write_bytes(b"lnk")

    monkeypatch.setattr(rt.subprocess, "run", fake_run)
    assert not rt.autostart_enabled()
    assert rt.set_autostart(True) is True
    assert rt.autostart_enabled()
    assert "escuta --se-ativado" in scripts[0]
    assert rt.SHORTCUT_NAME in scripts[0]
    assert rt.set_autostart(False) is True
    assert not rt.autostart_enabled()


def test_autostart_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "startup_dir", lambda: None)
    assert rt.set_autostart(True) is False
    assert rt.autostart_enabled() is False


def test_window_support_needs_windows_and_pywebview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert rt.window_supported() is False


def test_remote_busy_without_server_is_false() -> None:
    # Nada escuta nesta porta: a escuta não pode travar por isso.
    assert rt.remote_busy("http://127.0.0.1:9") is False
