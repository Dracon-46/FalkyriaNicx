"""Cada teste com o próprio ~/.nicx (projetos.json vazio)."""

from __future__ import annotations

import pytest

from nicx.projetos import deteccao


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    home = tmp_path / "nicx"
    home.mkdir()
    monkeypatch.setenv("NICX_HOME", str(home))
    deteccao.esquecer_intervalos()
    # Nenhum teste olha a janela de verdade.
    monkeypatch.setattr(deteccao, "sinal_da_janela", lambda info=None: None)
    yield home
    deteccao.esquecer_intervalos()


@pytest.fixture
def loja(home):
    from nicx.projetos.armazenamento import Projetos

    return Projetos()
