"""Registro de atividades: gravação, filtros, busca, integridade e limpeza."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from nicx.historico.registro import FALHOU, Registro, anotar, origem


@pytest.fixture
def r(tmp_path):
    banco = Registro(tmp_path / "historico.db")
    yield banco
    banco.fechar()


def test_anota_e_lista_do_mais_recente(r):
    a = r.anotar("nota", "Anotação: comprar pão")
    b = r.anotar("lembrete", "Lembrete criado: ligar para a mãe")
    itens = r.listar()
    assert [i.id for i in itens] == [b, a]
    assert itens[0].tipo == "lembrete" and itens[0].origem == "app"


def test_filtra_por_tipo_data_e_desfaziveis(r):
    velho = datetime.now() - timedelta(days=3)
    r.anotar("nota", "antiga", quando=velho)
    r.anotar("nota", "nova", desfazer={"tipo": "nota", "linha": "x"})
    r.anotar("acao", "Volume aumentado.")
    assert [i.titulo for i in r.listar(tipos=["nota"])] == ["nova", "antiga"]
    assert [
        i.titulo
        for i in r.listar(desde=datetime.now() - timedelta(days=1), tipos=["nota"])
    ] == ["nova"]
    desfaziveis = r.listar(so_desfaziveis=True)
    assert [i.titulo for i in desfaziveis] == ["nova"]
    assert desfaziveis[0].desfazivel


def test_falha_nao_e_desfazivel(r):
    r.anotar(
        "arquivo", "Arquivo alterado: x", resultado=FALHOU, desfazer={"tipo": "arquivo"}
    )
    assert r.ultima_desfazivel() is None


def test_busca_ignora_acentos_e_prefixo(r):
    r.anotar("nota", "Anotação: reunião com o João")
    r.anotar("nota", "Anotação: mercado")
    assert [i.titulo for i in r.listar(busca="reuniao")] == [
        "Anotação: reunião com o João"
    ]
    assert len(r.listar(busca="anot")) == 2
    assert r.listar(busca='"; DROP TABLE atividades; --') == []


def test_integridade_pega_edicao_por_fora(r):
    r.anotar("nota", "um")
    alvo = r.anotar("nota", "dois")
    r.anotar("nota", "três")
    assert r.verificar() == {"ok": True, "linhas": 3, "quebra_em": None}
    con = sqlite3.connect(r.caminho)
    con.execute("UPDATE atividades SET titulo = 'adulterado' WHERE id = ?", (alvo,))
    con.commit()
    con.close()
    assert r.verificar()["quebra_em"] == alvo


def test_limpeza_mantem_a_cadeia_valida(r):
    r.anotar("nota", "muito velha", quando=datetime.now() - timedelta(days=400))
    r.anotar("nota", "recente")
    assert r.limpar_antigas(30) == 1
    assert r.verificar()["ok"]
    assert r.limpar_antigas(0) == 0


def test_marcar_desfeito(r):
    a = r.anotar("nota", "x", desfazer={"tipo": "nota", "linha": "x"})
    r.marcar_desfeito(a)
    item = r.obter(a)
    assert item.desfeito_em is not None and not item.desfazivel


def test_origem_vale_dentro_do_bloco(r):
    with origem("voz"):
        a = r.anotar("acao", "Volume aumentado.")
    b = r.anotar("acao", "Volume diminuído.")
    assert r.obter(a).origem == "voz" and r.obter(b).origem == "app"


def test_atalho_respeita_config(monkeypatch, tmp_path):
    monkeypatch.setenv("NICX_HOME", str(tmp_path))
    from nicx.historico import config

    monkeypatch.setattr(config, "guardar_conversas", lambda: False)
    assert anotar("conversa", "oi") is None
    assert anotar("nota", "ok") is not None
    monkeypatch.setattr(config, "ligado", lambda: False)
    assert anotar("nota", "não") is None
