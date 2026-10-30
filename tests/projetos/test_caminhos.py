"""Caminhos de projeto comparados com as regras certas em qualquer sistema."""

from __future__ import annotations

from nicx.projetos import caminhos
from nicx.projetos.pedidos import _pasta_original


def test_caminho_do_windows_segue_o_windows_em_qualquer_sistema():
    assert caminhos.chave(r"C:\dev\Lumen") == caminhos.chave("c:/dev/lumen/")
    assert caminhos.nome(r"C:\dev\lumen") == "lumen"
    assert caminhos.separador(r"C:\dev") == "\\"


def test_caminho_posix_mantem_a_barra_inicial():
    assert caminhos.nome("/home/ana/site") == "site"
    assert caminhos.chave("/") in ("/", "\\")


def test_pasta_escrita_pelo_usuario_mantem_a_barra():
    assert _pasta_original("cria o projeto Site na pasta /tmp/x/site") == "/tmp/x/site"
    assert (
        _pasta_original(r"cria o projeto Site na pasta C:\dev\site.") == r"C:\dev\site"
    )
    assert _pasta_original("cria o projeto Site") == ""
