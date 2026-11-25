"""Exportar todos os meus dados: tudo da pessoa, nada de segredo."""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile

import pytest

from nicx.privacidade import exportar


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "nicx"
    (r / "skills" / "minha").mkdir(parents=True)
    (r / "connectors").mkdir()
    (r / "cache").mkdir()
    (r / "trabalho" / "abc" / "copias").mkdir(parents=True)
    (r / "notas.md").write_bytes("- comprar pão\n".encode())
    (r / "skills" / "minha" / "SKILL.md").write_bytes(b"# minha")
    (r / "config.toml").write_bytes(
        b'[engine]\ndefault = "ollama"\n[cloud]\napi_key = "sk-123"\ntoken = ""\n'
    )
    (r / "conta.bin").write_bytes(b"segredo")
    (r / ".vault_key").write_bytes(b"segredo")
    (r / "connectors" / "gmail.json").write_bytes(b'{"token": "x"}')
    (r / "cache" / "x.bin").write_bytes(b"cache")
    (r / "server.log").write_bytes(b"log")
    (r / "trabalho" / "abc" / "tarefa.json").write_bytes(b"{}")
    (r / "trabalho" / "abc" / "copias" / "0000_a.txt").write_bytes(b"copia")
    banco = sqlite3.connect(r / "memory.db")
    banco.execute("PRAGMA journal_mode=WAL")
    banco.execute("create table fatos (texto text)")
    banco.execute("insert into fatos values ('gosta de café')")
    banco.commit()  # fica no WAL: a cópia precisa trazer
    yield r
    banco.close()


def test_exporta_dados_e_deixa_segredos_de_fora(raiz):
    conversas = {"version": 1, "conversations": {"c1": {"title": "Oi"}}}
    dados, resumo = exportar.montar(conversas, raiz=raiz)
    z = zipfile.ZipFile(io.BytesIO(dados))
    nomes = set(z.namelist())
    assert {
        "LEIA-ME.txt",
        "conversas.json",
        "dados/notas.md",
        "dados/skills/minha/SKILL.md",
        "dados/config.toml",
        "dados/memory.db",
        "dados/trabalho/abc/tarefa.json",
    } <= nomes
    for fora in (
        "dados/conta.bin",
        "dados/.vault_key",
        "dados/connectors/gmail.json",
        "dados/cache/x.bin",
        "dados/server.log",
        "dados/trabalho/abc/copias/0000_a.txt",
    ):
        assert fora not in nomes
    assert json.loads(z.read("conversas.json"))["conversations"]["c1"]["title"] == "Oi"
    config = z.read("dados/config.toml").decode()
    assert "sk-123" not in config and 'api_key = "••••••"' in config
    assert 'token = ""' in config and 'default = "ollama"' in config
    leia = z.read("LEIA-ME.txt").decode()
    assert "conta.bin" in leia and "connectors/gmail.json" in leia
    assert set(resumo["fora"]) >= {"conta.bin", ".vault_key", "connectors/gmail.json"}

    copia = raiz.parent / "copia.db"
    copia.write_bytes(z.read("dados/memory.db"))
    banco = sqlite3.connect(copia)
    assert banco.execute("select texto from fatos").fetchall() == [("gosta de café",)]
    banco.close()


def test_rota(raiz, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.meus_dados import router

    monkeypatch.setenv("NICX_HOME", str(raiz))
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).post("/v1/meus-dados/exportar", json={"conversas": {"a": 1}})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "nicx-meus-dados-" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "dados/notas.md" in z.namelist() and "conversas.json" in z.namelist()
    ruim = TestClient(app).post("/v1/meus-dados/exportar", content=b"{nao")
    assert ruim.status_code == 422
