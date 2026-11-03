"""Controle de apps: frases, escolha do controle, segurança e o fluxo completo
(com a UI Automation simulada; ``test_janela_real`` usa uma janela de verdade)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from nicx.acoes import confirmacao, handle, parse
from nicx.acoes.intencoes import Action
from nicx.contexto import janela
from nicx.controle import servico, uia
from nicx.controle.uia import Elemento, Resultado

INFO = janela.InfoJanela(
    hwnd=5, titulo="Documento - Bloco de Notas", processo="notepad.exe"
)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield
    confirmacao.drop()


@pytest.mark.parametrize(
    ("frase", "op", "alvo", "texto"),
    [
        ("clica em Salvar", "clicar", "salvar", ""),
        ("clique no botão Enviar", "clicar", "enviar", ""),
        ("aperta o botão salvar", "clicar", "salvar", ""),
        ("abre o menu Arquivo", "menu", "arquivo", ""),
        ("vai na aba Revisão", "aba", "revisao", ""),
        ("marca a caixa Lembrar de mim", "marcar", "lembrar de mim", ""),
        ("desmarca a opção notificações", "desmarcar", "notificacoes", ""),
        (
            "escreve Falkyria Nicx no campo Pesquisar",
            "digitar",
            "pesquisar",
            "Falkyria Nicx",
        ),
        ("o que dá pra clicar aqui?", "listar", "", ""),
        ("click on Save", "clicar", "save", ""),
        ("press the OK button", "clicar", "ok", ""),
        ("open the File menu", "menu", "file", ""),
        ("check the Remember me box", "marcar", "remember me", ""),
        ("type hello into the search field", "digitar", "search", "hello"),
        ("haz clic en Guardar", "clicar", "guardar", ""),
        ("clique sur Enregistrer", "clicar", "enregistrer", ""),
    ],
)
def test_frases(frase, op, alvo, texto):
    assert parse(frase) == Action("ui", op, target=alvo, site=texto)


@pytest.mark.parametrize(
    ("frase", "kind"),
    [
        ("pausa a música", "media"),
        ("abre o chrome", "open"),
        ("fecha o chrome", "close"),
        ("me lembra de clicar em salvar daqui 5 minutos", "remind"),
    ],
)
def test_outras_acoes_continuam(frase, kind):
    assert parse(frase).kind == kind


def test_aperta_sem_botao_nao_e_clique():
    assert getattr(parse("aperta o play"), "kind", None) != "ui"


def test_escolha_pelo_nome():
    elementos = [
        Elemento("Salvar como...", "menu"),
        Elemento("Salvar", "botao"),
        Elemento("Salvar", "botao", visivel=False),
        Elemento("Avançado", "aba"),
    ]
    assert uia.escolher("salvar", elementos, ("botao",)) == 1  # igual e visível
    assert uia.escolher("salvar como", elementos) == 0
    assert uia.escolher("avancado", elementos, ("aba",)) == 3
    assert uia.escolher("imprimir", elementos) is None


@pytest.mark.parametrize(
    ("nome", "perigo"),
    [
        ("Excluir tudo", True),
        ("Enviar", True),
        ("Delete", True),
        ("Pagar agora", True),
        ("Salvar", False),
        ("Abrir", False),
        ("Configurações", False),
    ],
)
def test_perigoso(nome, perigo):
    assert servico.perigoso(nome) is perigo


# ----------------------------------------------------------------- fluxo
@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(servico.sys, "platform", "win32")
    monkeypatch.setattr(janela, "janela_de_fora", lambda: INFO)
    monkeypatch.setattr(janela, "sensivel", lambda _i: False)
    feitos: list[tuple[str, str, str]] = []
    botoes = [Elemento("Salvar", "botao"), Elemento("Excluir tudo", "botao")]

    def agir(hwnd, op, alvo, texto=""):
        indice = uia.escolher(alvo, botoes)
        if indice is None:
            return Resultado(uia.NAO_ACHEI, sugestoes=("Salvar",))
        feitos.append((op, botoes[indice].nome, texto))
        return Resultado(uia.FEITO, botoes[indice].nome, "botao")

    monkeypatch.setattr(uia, "agir", agir)
    monkeypatch.setattr(uia, "listar", lambda hwnd, prazo=None: botoes)
    return feitos


def test_clica(windows):
    saida = handle("clica em salvar")
    assert saida.ok and saida.message == 'Cliquei em "Salvar" no Bloco de Notas.'
    assert windows == [("clicar", "Salvar", "")]


def test_botao_perigoso_pede_confirmacao(windows):
    saida = handle("clica em tudo")
    assert "Excluir tudo" in saida.message and "confirmo" in saida.message
    assert windows == []
    assert handle("confirmo").ok and windows == [("clicar", "Excluir tudo", "")]


def test_nao_achou_sugere(windows):
    saida = handle("clica em imprimir")
    assert not saida.ok and "Tem: Salvar" in saida.message


def test_lista(windows):
    assert "Salvar, Excluir tudo" in handle("o que dá pra clicar aqui?").message


def test_janela_sensivel(windows, monkeypatch):
    monkeypatch.setattr(janela, "sensivel", lambda _i: True)
    assert "não mexo" in handle("clica em salvar").message and windows == []


def test_sem_janela(windows, monkeypatch):
    monkeypatch.setattr(janela, "janela_de_fora", lambda: None)
    assert "Não sei em qual janela" in handle("clica em salvar").message


def test_modelo_passa_pela_autonomia(windows, monkeypatch):
    from nicx.acoes.ferramenta import ComputerControlTool
    from nicx.historico import autonomia

    monkeypatch.setattr(autonomia, "nivel_atual", lambda: "assistido")
    ferramenta = ComputerControlTool()
    lista = ferramenta.execute(acao="botoes_da_janela")
    assert lista.success and "Salvar" in lista.content  # só ler não pede nada
    pedido = ferramenta.execute(acao="clicar_na_janela", alvo="Salvar")
    assert pedido.success and windows == []  # moderado no assistido: confirma antes
    assert handle("confirmo").ok and windows == [("clicar", "Salvar", "")]


def test_historico_sem_o_texto_digitado(windows):
    from nicx.historico.registro import registro

    handle("escreve minha frase secreta no campo pesquisar")
    atividades = [a.para_dict() for a in registro().listar()]
    assert atividades and "secreta" not in repr(atividades)


def test_textos_com_as_mesmas_chaves():
    from nicx.controle import textos

    chaves = textos.chaves()
    assert all(c == chaves["pt-BR"] for c in chaves.values())


# --------------------------------------------------------- janela de verdade
_JANELA = r"""
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.Text = 'Nicx Teste Controle'
$b = New-Object System.Windows.Forms.Button
$b.Text = 'Salvar'
$b.add_Click({ $f.Text = 'Nicx Teste Controle - salvo' })
$c = New-Object System.Windows.Forms.CheckBox
$c.Text = 'Lembrar de mim'; $c.Top = 40; $c.Width = 200
$f.Controls.AddRange(@($b, $c))
[System.Windows.Forms.Application]::Run($f)
"""


@pytest.mark.skipif(
    sys.platform != "win32" or bool(os.environ.get("CI")),
    reason="abre uma janela de verdade (só no Windows, fora do CI)",
)
def test_janela_real(tmp_path):
    if not uia._uia():
        pytest.skip("sem UI Automation (pythonnet)")
    script = tmp_path / "janela.ps1"
    script.write_text(_JANELA, encoding="utf-8-sig")
    proc = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-STA",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        creationflags=0x08000000,
    )
    try:
        hwnd = 0
        for _ in range(80):
            hwnd = ctypes.windll.user32.FindWindowW(None, "Nicx Teste Controle")
            if hwnd:
                break
            time.sleep(0.25)
        assert hwnd
        nomes = [e.nome for e in uia.listar(hwnd)]
        assert "Salvar" in nomes and "Lembrar de mim" in nomes
        assert uia.agir(hwnd, "marcar", "lembrar").estado == uia.FEITO
        assert uia.agir(hwnd, "marcar", "lembrar").estado == uia.JA_ESTAVA
        assert uia.agir(hwnd, "clicar", "salvar").estado in (uia.FEITO, uia.TALVEZ)
        for _ in range(20):
            if ctypes.windll.user32.FindWindowW(None, "Nicx Teste Controle - salvo"):
                break
            time.sleep(0.25)
        assert ctypes.windll.user32.FindWindowW(None, "Nicx Teste Controle - salvo")
    finally:
        proc.kill()


def test_pasta_dos_testes():
    assert Path(__file__).parent.name == "controle"
