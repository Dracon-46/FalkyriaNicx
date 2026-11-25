"""Pesquisar em tudo: uma busca só por projetos, notas, agenda, memória..."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from nicx.busca import servico


@pytest.fixture
def dados(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    from nicx.acoes import agenda, lembretes, notas
    from nicx.memoria.store import LocalFactStore
    from nicx.projetos.armazenamento import Projetos

    Projetos().criar("Reforma da cozinha", objetivo="Trocar o piso e os armários")
    notas.add("Orçamento do piso: pedir para o João")
    lembretes.add(
        "Ligar para o marceneiro dos armários", datetime.now() + timedelta(days=1)
    )
    agenda.add("Visita da loja de pisos", datetime.now() + timedelta(days=2))
    LocalFactStore().add("Prefere piso de madeira clara", source="teste")
    notas.add("Comprar café")
    yield


def test_normaliza_e_exige_todas_as_palavras():
    assert servico.palavras("Cozinha, PISO!") == ["cozinha", "piso"]
    assert servico.casa("Orçamento do piso", servico.palavras("orcamento piso")) == 2
    assert servico.casa("Orçamento do piso", servico.palavras("piso cozinha")) == 0
    texto = "a " * 200 + "achei o piso aqui " + "b " * 200
    t = servico.trecho(texto, ["piso"], 60)
    assert "piso" in t and t.startswith("…") and t.endswith("…")


def test_busca_em_todas_as_fontes(dados):
    r = servico.buscar("piso")
    fontes = {x["fonte"] for x in r["resultados"]}
    assert {"projeto", "nota", "compromisso", "memoria"} <= fontes
    assert r["falharam"] == []
    projeto = next(x for x in r["resultados"] if x["fonte"] == "projeto")
    assert projeto["titulo"] == "Reforma da cozinha" and projeto["link"] == "/projetos"
    assert "Trocar o piso" in projeto["trecho"]
    assert all("café" not in x["titulo"] for x in r["resultados"])

    r = servico.buscar("marceneiro armarios")
    # O lembrete e a anotação dele no histórico.
    assert [x["fonte"] for x in r["resultados"]] == ["lembrete", "historico"]
    assert servico.buscar("x")["resultados"] == []  # curta demais


def test_fonte_quebrada_nao_derruba(dados, monkeypatch):
    def quebra(_termos):
        raise RuntimeError("arquivo estragado")

    monkeypatch.setitem(servico.FONTES, "nota", quebra)
    r = servico.buscar("piso")
    assert r["falharam"] == ["nota"]
    assert any(x["fonte"] == "projeto" for x in r["resultados"])


def test_rota(dados):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.busca import router

    app = FastAPI()
    app.include_router(router)
    http = TestClient(app)
    r = http.get("/v1/busca", params={"q": "piso", "fontes": "nota,projeto"})
    assert r.status_code == 200
    assert {x["fonte"] for x in r.json()["resultados"]} == {"nota", "projeto"}
