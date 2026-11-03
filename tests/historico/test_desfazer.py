"""Desfazer unificado sobre os dados reais (lembretes, agenda, notas, pastas...)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from nicx.acoes import agenda, arquivos, confirmacao, lembretes, notas
from nicx.historico import ferramentas, mudancas
from nicx.historico.desfazer import desfazer
from nicx.historico.registro import registro


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"
    confirmacao.drop()


def test_nada_para_desfazer():
    ok, frase = desfazer()
    assert not ok and frase == "Não há nada para desfazer."


def test_lembrete_criado_e_cancelado():
    quando = datetime.now() + timedelta(hours=2)
    r = lembretes.add("ligar para a mãe", quando)
    ok, frase = desfazer()
    assert ok and "ligar para a mãe" in frase
    assert lembretes.pending() == []
    # cancelar e desfazer devolve o lembrete
    r = lembretes.add("pagar a conta", quando)
    assert lembretes.cancel_id(r.id)
    assert desfazer()[0]
    assert [x.text for x in lembretes.pending()] == ["pagar a conta"]
    ok, frase = desfazer(registro().listar(tipos=["lembrete"])[-1].id)
    assert not ok and frase == "Isso já foi desfeito."


def test_desfazer_nao_perde_o_que_veio_depois():
    quando = datetime.now() + timedelta(hours=2)
    primeiro = lembretes.add("primeiro", quando)
    lembretes.add("segundo", quando)
    alvo = registro().listar(tipos=["lembrete"])[-1]  # a criação do primeiro
    assert desfazer(alvo.id)[0]
    assert [x.text for x in lembretes.pending()] == ["segundo"]
    assert primeiro.id not in {x.id for x in lembretes.pending()}


def test_compromisso_volta_com_o_aviso():
    agora = datetime.now()
    agenda.add("dentista", agora + timedelta(days=1), now=agora)
    assert len(lembretes.pending()) == 1  # o aviso de 15 min antes
    linhas = registro().listar(tipos=["lembrete"])
    assert linhas == []  # o aviso foi junto com o compromisso, não virou linha própria
    assert desfazer()[0]
    assert agenda._load() == [] and lembretes.pending() == []


def test_compromisso_desmarcado_volta():
    agora = datetime.now()
    evento = agenda.add("dentista", agora + timedelta(days=1), now=agora)
    agenda.cancel(evento)
    assert agenda._load() == [] and lembretes.pending() == []
    assert desfazer()[0]
    assert [e.title for e in agenda._load()] == ["dentista"]
    assert len(lembretes.pending()) == 1


def test_anotacao_e_limpeza():
    notas.add("comprar pão")
    notas.add("ligar para o banco")
    assert desfazer()[0]
    assert notas.all_notes() == ["comprar pão"]
    notas.clear()
    assert notas.all_notes() == []
    assert desfazer()[0]
    assert notas.all_notes() == ["comprar pão"]


def test_organizacao_de_pasta(tmp_path):
    pasta = tmp_path / "Downloads"
    pasta.mkdir()
    (pasta / "foto.jpg").write_bytes(b"x")
    (pasta / "nota.pdf").write_bytes(b"x")
    velho = (datetime.now() - timedelta(days=2)).timestamp()
    for f in pasta.iterdir():
        os.utime(f, (velho, velho))  # arquivos recém-baixados ficam onde estão
    movidos, _log = arquivos.organize(pasta, arquivos.plan(pasta))
    assert movidos == 2 and not (pasta / "foto.jpg").exists()
    ok, frase = desfazer()
    assert ok and "Downloads" in frase
    assert (pasta / "foto.jpg").exists() and (pasta / "nota.pdf").exists()


def test_projeto_criado(home):
    from nicx.projetos.armazenamento import Projetos

    projetos = Projetos()
    projetos.criar("Site novo")
    assert [p.nome for p in projetos.listar()] == ["Site novo"]
    assert desfazer()[0]
    assert projetos.listar() == []


def test_arquivo_escrito_por_ferramenta(tmp_path):
    alvo = tmp_path / "texto.txt"
    alvo.write_text("antes", encoding="utf-8")
    novo = tmp_path / "novo.txt"
    for caminho, conteudo in ((alvo, "depois"), (novo, "criado")):
        params = {"path": str(caminho), "content": conteudo}
        planos = ferramentas.copia_antes("file_write", params)
        caminho.write_text(conteudo, encoding="utf-8")
        ferramentas.anotar_chamada(
            "file_write", params, True, "ok", nivel="autonomo", planos=planos
        )
    assert desfazer()[0]  # o arquivo novo sai (vai para a pasta do desfazer)
    assert not novo.exists()
    assert desfazer()[0]
    assert alvo.read_text(encoding="utf-8") == "antes"


def test_mudancas_inverter_preserva_o_resto():
    antes = [{"id": "a", "v": 1}, {"id": "b", "v": 1}]
    depois = [{"id": "a", "v": 2}, {"id": "c", "v": 1}]
    m = mudancas.diferenca("x", antes, depois)
    atuais = depois + [{"id": "d", "v": 1}]  # "d" chegou depois
    assert mudancas.inverter(m, atuais) == [
        {"id": "a", "v": 1},
        {"id": "d", "v": 1},
        {"id": "b", "v": 1},
    ]
    assert mudancas.diferenca("x", antes, antes) is None


def test_lembrete_que_tocou_nao_vira_historico():
    lembretes.add("agora", datetime.now() - timedelta(minutes=1))
    antes = len(registro().listar())
    assert len(lembretes.pop_due()) == 1
    assert len(registro().listar()) == antes
