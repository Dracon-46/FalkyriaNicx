"""Cada teste do resumo com um ~/.nicx vazio, sem projetos e sem conectores."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from nicx.acoes import calendarios


@pytest.fixture(autouse=True)
def nicx_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("NICX_HOME", str(home))
    cfg = SimpleNamespace(calendario_padrao="windows", fuso="America/Sao_Paulo")
    monkeypatch.setattr(calendarios, "_config_agenda", lambda: cfg)
    monkeypatch.setattr(calendarios, "eventos_conectados", lambda day: [])
    # Sem o módulo de projetos (o teste que precisa põe um falso).
    monkeypatch.setitem(sys.modules, "nicx.projetos", None)
    return home
