"""Opções de administrador escondidas até o banco confirmar a conta.

Esconder é só para não confundir: quem protege é o banco (regras de linha com
nicx_is_admin) e a chave privada da Falkyria. Aqui: na dúvida, escondido.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from nicx.conta import cliente, cofre, servico


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    with servico._LOCK:
        servico._ADMIN_CACHE.update(uid=None, ate=0.0, admin=False)
    sessao = {
        "access_token": "t",
        "refresh_token": "r",
        "expires_at": 4102444800,
        "email": "pessoa@exemplo.com",
        "user_id": "u1",
    }
    monkeypatch.setattr(cofre, "ler", lambda: dict(sessao))
    yield


def test_sem_conta_nao_e_admin(monkeypatch):
    monkeypatch.setattr(cofre, "ler", lambda: None)
    monkeypatch.setattr(
        cliente, "rpc", lambda *a, **k: pytest.fail("não devia perguntar")
    )
    assert servico.e_admin() is False


def test_banco_confirma_admin_e_guarda(monkeypatch):
    chamadas = []

    def rpc(funcao, token, argumentos=None):
        chamadas.append(funcao)
        return {"admin": True, "aal": "aal1"}

    monkeypatch.setattr(cliente, "rpc", rpc)
    assert servico.e_admin() is True
    assert servico.e_admin() is True
    assert chamadas == ["nicx_admin_status"]  # guardado por 10 minutos


@pytest.mark.parametrize("resposta", [{"admin": False}, {"admin": "true"}, None, []])
def test_qualquer_outra_resposta_esconde(monkeypatch, resposta):
    monkeypatch.setattr(cliente, "rpc", lambda *a, **k: resposta)
    assert servico.e_admin() is False


def test_erro_esconde(monkeypatch):
    def falha(*a, **k):
        raise cliente.ContaErro("sem internet")

    monkeypatch.setattr(cliente, "rpc", falha)
    assert servico.e_admin() is False


def test_rota(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.conta import router

    monkeypatch.setattr(cliente, "rpc", lambda *a, **k: {"admin": False})
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/v1/conta/admin").json() == {"admin": False}


def test_comandos_da_falkyria_fora_da_ajuda():
    from nicx.comandos import cli

    ajuda = CliRunner().invoke(cli, ["--help"]).output
    assert "loja" not in ajuda.split("Comandos")[-1]
    sub = CliRunner().invoke(cli, ["atualizacao", "--help"]).output
    assert "procurar" in sub and "assinar" not in sub and "novidades" not in sub
