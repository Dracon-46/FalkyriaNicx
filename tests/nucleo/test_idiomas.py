"""Tabela de idiomas: interface, Whisper e voz do Kokoro."""

from __future__ import annotations

import pytest

from nicx.nucleo.idiomas import IDIOMAS, PADRAO, idioma, instrucao_resposta


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("pt-BR", "pt-BR"),
        ("pt", "pt-BR"),
        ("pt-PT", "pt-BR"),
        ("en-US", "en"),
        ("es-MX", "es"),
        ("zh", "zh"),
        ("ar", "ar"),
        ("xx", PADRAO),
        (None, PADRAO),
        ("", PADRAO),
    ],
)
def test_codigos_viram_o_idioma_certo(codigo, esperado):
    assert idioma(codigo).codigo == esperado


def test_portugues_nao_pede_nada_e_os_outros_pedem():
    assert instrucao_resposta("pt-BR") == ""
    assert instrucao_resposta(None) == ""
    for codigo in IDIOMAS:
        if codigo != PADRAO:
            assert IDIOMAS[codigo].nome in instrucao_resposta(codigo)


def test_cada_voz_do_kokoro_bate_com_o_idioma():
    # O prefixo da voz do Kokoro diz a língua: p=português, e=espanhol...
    prefixos = {"pt-BR": "p", "en": "a", "es": "e", "zh": "z", "hi": "h", "fr": "f"}
    for codigo, prefixo in prefixos.items():
        assert IDIOMAS[codigo].voz_kokoro.startswith(prefixo)
    assert IDIOMAS["ar"].voz_kokoro == ""  # o Kokoro não fala árabe
