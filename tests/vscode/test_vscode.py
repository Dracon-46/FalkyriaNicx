"""Conectar ao VS Code: achar o `code` e instalar a extensão do Nicx."""

from __future__ import annotations

import subprocess

import pytest

from nicx.vscode import servico


class _Code:
    """Um `code` falso: registra os comandos e devolve o combinado."""

    def __init__(self, lista="", codigo=0, erro=""):
        self.lista = lista
        self.codigo = codigo
        self.erro = erro
        self.chamadas = []

    def __call__(self, code, *args, timeout=120.0):
        self.chamadas.append(args)
        if args[0] == "--list-extensions":
            return subprocess.CompletedProcess(args, 0, self.lista, "")
        return subprocess.CompletedProcess(args, self.codigo, "", self.erro)


@pytest.fixture
def com_vscode(tmp_path, monkeypatch):
    code = tmp_path / "code.cmd"
    code.write_text("@echo off", encoding="utf-8")
    vsix = tmp_path / "nicx.vsix"
    vsix.write_bytes(b"PK")
    monkeypatch.setattr(servico, "_candidatos", lambda: [code])
    monkeypatch.setattr(servico, "_PACOTE", vsix)
    return code, vsix


def test_estado_com_extensao_instalada(com_vscode, monkeypatch):
    falso = _Code(lista="ms-python.python@2026.1.0\nFalkyria.nicx@0.1.0\n")
    monkeypatch.setattr(servico, "_rodar", falso)
    assert servico.estado() == {"vscode": True, "pacote": True, "instalada": "0.1.0"}


def test_instalar_chama_o_code_com_o_pacote(com_vscode, monkeypatch):
    _code, vsix = com_vscode
    falso = _Code(lista="falkyria.nicx@0.1.0")
    monkeypatch.setattr(servico, "_rodar", falso)
    assert servico.instalar()["instalada"] == "0.1.0"
    assert ("--install-extension", str(vsix), "--force") in falso.chamadas


def test_sem_vscode_avisa(monkeypatch, tmp_path):
    vsix = tmp_path / "nicx.vsix"
    vsix.write_bytes(b"PK")
    monkeypatch.setattr(servico, "_PACOTE", vsix)
    monkeypatch.setattr(servico, "_candidatos", lambda: [])
    assert servico.estado() == {"vscode": False, "pacote": True, "instalada": None}
    with pytest.raises(servico.VSCodeErro, match="não achei o VS Code"):
        servico.instalar()


def test_sem_pacote_avisa(com_vscode, monkeypatch, tmp_path):
    monkeypatch.setattr(servico, "_PACOTE", tmp_path / "nao-existe.vsix")
    with pytest.raises(servico.VSCodeErro, match="não veio"):
        servico.instalar()


def test_vscode_recusa(com_vscode, monkeypatch):
    monkeypatch.setattr(servico, "_rodar", _Code(codigo=1, erro="linha 1\nCorrupt ZIP"))
    with pytest.raises(servico.VSCodeErro, match="Corrupt ZIP"):
        servico.instalar()


def test_rotas(com_vscode, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.vscode import router

    monkeypatch.setattr(servico, "_rodar", _Code(lista=""))
    app = FastAPI()
    app.include_router(router)
    http = TestClient(app)
    assert http.get("/v1/vscode").json() == {
        "vscode": True,
        "pacote": True,
        "instalada": None,
    }
    assert http.post("/v1/vscode/instalar").status_code == 200
    monkeypatch.setattr(servico, "_candidatos", lambda: [])
    resposta = http.post("/v1/vscode/instalar")
    assert resposta.status_code == 409 and "VS Code" in resposta.json()["detail"]
