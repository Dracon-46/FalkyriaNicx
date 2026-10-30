"""Texto do ditado: comandos de voz e limpeza (sem sistema, sem modelo)."""

from __future__ import annotations

import pytest

from nicx.ditado.comandos import COMANDOS, comandos_para, limpar, preparar_texto
from nicx.nucleo.idiomas import IDIOMAS


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        # O Whisper pontua o próprio comando; a pontuação extra sai.
        ("tudo bem, vírgula, como vai", "tudo bem, como vai"),
        ("como vai ponto final obrigado", "como vai. Obrigado"),
        ("Fim. Ponto final.", "Fim."),
        ("Linha um. Nova linha. linha dois", "Linha um.\nLinha dois"),
        ("olá, próxima linha, tchau", "olá\nTchau"),
        ("primeiro novo parágrafo segundo", "primeiro\n\nSegundo"),
        # Sem acento (o Whisper às vezes escreve assim) e maiúsculas.
        ("um virgula dois", "um, dois"),
        ("um VÍRGULA dois", "um, dois"),
        # O Whisper achou que a frase acabou: a palavra seguinte não é começo.
        ("Ok. Vírgula. Então vamos", "Ok, então vamos"),
        ("Ok. Vírgula. ONU", "Ok, ONU"),
        # Só o comando: digita a quebra de linha.
        ("Nova linha.", "\n"),
    ],
)
def test_comandos_em_portugues(bruto: str, esperado: str) -> None:
    assert preparar_texto(bruto, "pt-BR") == esperado


def test_palavra_parecida_nao_e_comando() -> None:
    assert preparar_texto("a linha nova chegou", "pt-BR") == "a linha nova chegou"
    assert preparar_texto("vírgulas e pontos", "pt-BR") == "vírgulas e pontos"


def test_idioma_escolhido_e_portugues() -> None:
    assert preparar_texto("hello comma world full stop bye", "en") == (
        "hello, world. Bye"
    )
    # O português vale junto do idioma escolhido.
    assert preparar_texto("hello vírgula world", "en") == "hello, world"
    assert preparar_texto("Hola coma qué tal nueva línea adiós", "es") == (
        "Hola, qué tal\nAdiós"
    )
    assert preparar_texto("bonjour virgule à la ligne merci", "fr") == (
        "bonjour,\nMerci"
    )
    # Chinês: sem espaço entre palavras e com a pontuação de lá.
    assert preparar_texto("你好逗号世界句号", "zh") == "你好，世界。"
    # Inglês não vale no português.
    assert preparar_texto("um comma dois", "pt-BR") == "um comma dois"


def test_todos_os_idiomas_tem_os_comandos() -> None:
    assert set(COMANDOS) == set(IDIOMAS)
    for cmds in COMANDOS.values():
        assert set(cmds.frases) == {"linha", "paragrafo", "ponto", "virgula"}
    assert len(comandos_para("pt-BR")) == 1
    assert len(comandos_para("en")) == 2


@pytest.mark.parametrize(
    "bruto",
    ["", "   ", "...", " . , ", "Legendas pela comunidade Amara.org"],
)
def test_ruido_nao_digita_nada(bruto: str) -> None:
    assert preparar_texto(bruto, "pt-BR") == ""


def test_limpa_espacos_sobrando() -> None:
    assert limpar("  oi   tudo  bem ,  sim .  ") == "oi tudo bem, sim."
    assert limpar("a  \n   b") == "a\nb"
    assert preparar_texto("  Olá,   mundo.  ", "pt-BR") == "Olá, mundo."
