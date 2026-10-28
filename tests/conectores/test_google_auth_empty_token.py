"""Conta Google sem token: erro claro em vez de cabeçalho "Bearer " vazio."""

from __future__ import annotations

import json

import pytest

from nicx.conectores.google_auth import GoogleAuthError, call_with_refresh


def test_sem_token_e_sem_refresh_avisa_que_falta_conectar(tmp_path):
    cred = tmp_path / "google.json"
    cred.write_text(json.dumps({"client_id": "x"}), encoding="utf-8")
    chamadas = []
    with pytest.raises(GoogleAuthError):
        call_with_refresh(lambda token: chamadas.append(token), str(cred))
    assert chamadas == []
