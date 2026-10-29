"""Combinações do atalho global: leitura, forma canônica e recusas."""

from __future__ import annotations

import pytest

from nicx.atalho.teclas import CombinacaoInvalida, ler_combinacao, normalizar


@pytest.mark.parametrize(
    ("entrada", "texto", "rotulo"),
    [
        ("ctrl+alt+n", "ctrl+alt+n", "Ctrl + Alt + N"),
        ("Alt + Ctrl + N", "ctrl+alt+n", "Ctrl + Alt + N"),
        ("control+shift+space", "ctrl+shift+space", "Ctrl + Shift + Espaço"),
        ("win+alt+f9", "alt+win+f9", "Alt + Win + F9"),
        ("ctrl+alt+5", "ctrl+alt+5", "Ctrl + Alt + 5"),
        ("ctrl+shift+pgup", "ctrl+shift+pageup", "Ctrl + Shift + PageUp"),
    ],
)
def test_le_e_normaliza(entrada: str, texto: str, rotulo: str) -> None:
    combinacao = ler_combinacao(entrada)
    assert combinacao.texto == texto
    assert combinacao.rotulo == rotulo
    assert normalizar(entrada) == texto


def test_codigos_do_windows() -> None:
    combinacao = ler_combinacao("ctrl+alt+n")
    assert combinacao.bits_modificadores == 0x0002 | 0x0001
    assert combinacao.codigo_virtual == ord("N")
    assert ler_combinacao("ctrl+alt+f1").codigo_virtual == 0x70
    assert ler_combinacao("alt+win+f24").codigo_virtual == 0x87
    assert ler_combinacao("ctrl+shift+space").codigo_virtual == 0x20


@pytest.mark.parametrize(
    ("entrada", "trecho"),
    [
        ("n", "Ctrl, Alt ou Win"),
        ("f5", "Ctrl, Alt ou Win"),
        ("shift+a", "Ctrl, Alt ou Win"),
        ("ctrl+alt", "Falta a tecla principal"),
        ("ctrl+a+b", "só uma tecla"),
        ("ctrl+ctrl+n", "repetido"),
        ("ctrl+alt+ç", "não suportada"),
        ("ctrl++n", "mal escrita"),
        ("", "Escolha"),
    ],
)
def test_recusa_combinacoes_invalidas(entrada: str, trecho: str) -> None:
    with pytest.raises(CombinacaoInvalida, match=trecho):
        ler_combinacao(entrada)


@pytest.mark.parametrize(
    "entrada",
    [
        "ctrl+alt+del",
        "ctrl+alt+delete",
        "win+l",
        "alt+tab",
        "alt+f4",
        "ctrl+shift+esc",
        "ctrl+c",
        "ctrl+v",
        "win+d",
        "shift+win+s",
    ],
)
def test_recusa_combinacoes_do_sistema(entrada: str) -> None:
    with pytest.raises(CombinacaoInvalida, match="do sistema ou de uso geral"):
        ler_combinacao(entrada)


def test_config_padrao_e_toml(tmp_path) -> None:
    from nicx.nucleo.config import AtalhoConfig, load_config

    padrao = AtalhoConfig()
    assert padrao.ativo is False  # só o usuário liga
    assert normalizar(padrao.teclas) == "ctrl+alt+n"
    assert padrao.acao == "flutuante"

    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        '[atalho]\nativo = true\nteclas = "ctrl+shift+space"\nacao = "app"\n',
        encoding="utf-8",
    )
    load_config.cache_clear()
    try:
        cfg = load_config(arquivo)
    finally:
        load_config.cache_clear()
    assert cfg.atalho.ativo is True
    assert cfg.atalho.teclas == "ctrl+shift+space"
    assert cfg.atalho.acao == "app"
