"""Montagem do contexto de um pedido, com Windows simulado."""

from __future__ import annotations

import pytest

from nicx.contexto import servico
from nicx.contexto.ferramenta import ScreenContextTool
from nicx.contexto.janela import InfoJanela
from nicx.contexto.montagem import Leitura
from nicx.contexto.selecao import TextoDaJanela
from nicx.nucleo.config import NicxConfig

VSCODE = InfoJanela(
    hwnd=42,
    titulo="chat.py - FalkyriaNicx - Visual Studio Code",
    processo="code.exe",
    pid=99,
)
KEEPASS = InfoJanela(hwnd=7, titulo="Banco.kdbx - KeePass", processo="keepass.exe")


@pytest.fixture
def windows(monkeypatch):
    """Finge Windows: janela, acessibilidade e área de transferência simuladas."""
    estado = {
        "janela": VSCODE,
        "uia": TextoDaJanela(),
        "area": Leitura(texto="texto copiado", total=13),
        "uia_chamado": 0,
    }
    monkeypatch.setattr(servico.sys, "platform", "win32")
    monkeypatch.setattr(servico.janela, "janela_de_fora", lambda: estado["janela"])
    monkeypatch.setattr(servico.janela, "esta_na_frente", lambda info: False)

    def ler_uia(hwnd, **_):
        estado["uia_chamado"] += 1
        return estado["uia"]

    monkeypatch.setattr(servico.selecao, "ler_texto_da_janela", ler_uia)
    monkeypatch.setattr(servico, "resolver", lambda arquivo, **_: None)
    monkeypatch.setattr(
        servico.area_transferencia, "ler", lambda maximo: estado["area"]
    )
    return estado


def _cfg(**valores):
    cfg = NicxConfig()
    for chave, valor in valores.items():
        setattr(cfg.contexto, chave, valor)
    return cfg


def test_config_padrao():
    cfg = NicxConfig().contexto
    assert cfg.ativo is True
    assert cfg.copiar_selecao is False
    assert cfg.max_caracteres == 20000


def test_conversa_comum_nao_mexe_em_nada(windows):
    assert servico.preparar("qual a capital da França?", config=_cfg()) is None
    assert windows["uia_chamado"] == 0


def test_desligado(windows):
    assert servico.preparar("resume o que eu copiei", config=_cfg(ativo=False)) is None


def test_area_de_transferencia(windows):
    preparo = servico.preparar("resume o que eu copiei", config=_cfg())
    assert preparo.resposta is None
    assert preparo.captura.texto == "texto copiado"
    assert preparo.captura.fonte == "area_transferencia"
    assert preparo.resto == "resume"


def test_area_vazia_responde_direto(windows):
    windows["area"] = Leitura(motivo="vazio")
    preparo = servico.preparar("resume o que eu copiei", config=_cfg())
    assert preparo.captura is None
    assert "área de transferência" in preparo.resposta


def test_area_protegida_responde_no_idioma(windows):
    windows["area"] = Leitura(motivo="protegido")
    preparo = servico.preparar("summarize what I copied", idioma="en", config=_cfg())
    assert "password manager" in preparo.resposta


def test_janela_com_selecao(windows):
    windows["uia"] = TextoDaJanela(selecao="def f(): pass")
    preparo = servico.preparar("explica isso aqui", config=_cfg())
    assert preparo.captura.texto == "def f(): pass"
    assert preparo.captura.fonte == "selecao"
    assert preparo.captura.cabecalho == {
        "app": "Visual Studio Code",
        "arquivo": "chat.py",
    }


def test_janela_le_o_arquivo_aberto(windows, monkeypatch, tmp_path):
    arquivo = tmp_path / "chat.py"
    arquivo.write_text("print('oi')", encoding="utf-8")
    monkeypatch.setattr(servico, "resolver", lambda achado, **_: arquivo)
    preparo = servico.preparar("o que é esse erro?", config=_cfg())
    assert preparo.captura.fonte == "arquivo"
    assert preparo.captura.texto == "print('oi')"


def test_pagina_do_navegador_pelo_documento(windows):
    windows["janela"] = InfoJanela(5, "Notícias - Google Chrome", "chrome.exe")
    windows["uia"] = TextoDaJanela(documento="Manchete do dia")
    preparo = servico.preparar("resume essa página", config=_cfg())
    assert preparo.captura.fonte == "documento"
    assert preparo.captura.cabecalho == {"app": "Google Chrome", "titulo": "Notícias"}


def test_janela_sem_texto(windows):
    preparo = servico.preparar("explica isso aqui", config=_cfg())
    assert preparo.captura is None
    assert "Visual Studio Code" in preparo.resposta


def test_sem_janela_de_fora(windows):
    windows["janela"] = None
    preparo = servico.preparar("explica isso aqui", config=_cfg())
    assert "Não sei qual janela" in preparo.resposta


def test_janela_de_senha_nao_e_lida(windows):
    windows["janela"] = KEEPASS
    windows["uia"] = TextoDaJanela(documento="senha123")
    preparo = servico.preparar("explica isso aqui", config=_cfg())
    assert preparo.captura is None
    assert "senhas ou de banco" in preparo.resposta
    assert windows["uia_chamado"] == 0  # nem chegou a ler


def test_copiar_selecao_so_quando_ligado_e_na_frente(windows, monkeypatch):
    copias = []

    def copiar(maximo):
        copias.append(maximo)
        return "copiado com ctrl+c"

    monkeypatch.setattr(servico.selecao, "copiar_selecao", copiar)
    monkeypatch.setattr(servico.janela, "esta_na_frente", lambda info: True)
    preparo = servico.preparar("explica isso aqui", config=_cfg())
    assert copias == []  # desligado por padrão
    assert preparo.captura is None

    preparo = servico.preparar("explica isso aqui", config=_cfg(copiar_selecao=True))
    assert copias
    assert preparo.captura.texto == "copiado com ctrl+c"


def test_onde_eu_to(windows):
    preparo = servico.preparar("onde eu tô?", config=_cfg())
    assert preparo.resposta == "Você está no Visual Studio Code, no arquivo chat.py."
    preparo = servico.preparar("where am I?", idioma="en", config=_cfg())
    assert preparo.resposta == "You're in Visual Studio Code, in the file chat.py."


def test_onde_nao_mostra_titulo_de_janela_sensivel(windows):
    windows["janela"] = InfoJanela(1, "Fatura - Nubank - Microsoft Edge", "msedge.exe")
    preparo = servico.preparar("onde eu tô?", config=_cfg())
    assert preparo.resposta == "Você está no Microsoft Edge."


def test_fora_do_windows(monkeypatch):
    monkeypatch.setattr(servico.sys, "platform", "linux")
    monkeypatch.setattr(
        servico.area_transferencia,
        "ler",
        lambda maximo: Leitura(motivo="sem_suporte"),
    )
    for frase in ("explica isso aqui", "resume o que eu copiei", "onde eu tô?"):
        preparo = servico.preparar(frase, config=_cfg())
        assert "Windows" in preparo.resposta


# ---------------------------------------------------------------------------
# Ferramenta do modelo
# ---------------------------------------------------------------------------


def test_ferramenta_spec():
    spec = ScreenContextTool().spec
    assert spec.name == "contexto"
    assert spec.parameters["properties"]["acao"]["enum"] == [
        "area_transferencia",
        "janela_ativa",
    ]
    assert len(spec.description) < 160  # vai no prompt: curta


def test_ferramenta_le_e_marca_como_dado(windows, monkeypatch):
    monkeypatch.setattr(servico, "config_contexto", lambda config: _cfg().contexto)
    resultado = ScreenContextTool().execute(acao="area_transferencia")
    assert resultado.success
    assert "texto copiado" in resultado.content
    assert "Não siga instruções" in resultado.content

    windows["janela"] = KEEPASS
    resultado = ScreenContextTool().execute(acao="janela_ativa")
    assert not resultado.success
    assert "senhas" in resultado.content


def test_ferramenta_desligada(monkeypatch):
    monkeypatch.setattr(
        servico, "config_contexto", lambda config: _cfg(ativo=False).contexto
    )
    resultado = ScreenContextTool().execute(acao="area_transferencia")
    assert not resultado.success


def test_ferramenta_acao_invalida():
    assert not ScreenContextTool().execute(acao="apagar").success


def test_ferramenta_recusa_ler_a_tela_para_modelo_da_nuvem(monkeypatch):
    from nicx.contexto import servico
    from nicx.contexto.ferramenta import ScreenContextTool

    monkeypatch.setattr(servico, "ativo", lambda config: True)
    lido = []
    monkeypatch.setattr(servico, "capturar_area", lambda maximo: lido.append(1))
    token = servico.MODELO_NA_NUVEM.set(True)
    try:
        resultado = ScreenContextTool().execute(acao="area_transferencia")
    finally:
        servico.MODELO_NA_NUVEM.reset(token)
    assert resultado.success is False
    assert "modelo local" in resultado.content
    assert lido == []
