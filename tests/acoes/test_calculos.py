"""Calculadora em linguagem natural: porcentagens, contas, conta dividida e datas."""

from __future__ import annotations

from datetime import datetime

import pytest

from nicx.acoes import calculos, intencoes

AGORA = datetime(2026, 11, 25, 10)  # quarta-feira


@pytest.mark.parametrize(
    "frase, resposta",
    [
        ("quanto é 15% de 230", "15% de 230 é 34,50."),
        ("15 por cento de 230", "15% de 230 é 34,50."),
        (
            "quanto fica 230 com 15% de desconto",
            "230 com 15% de desconto fica 195,50 (desconto de 34,50).",
        ),
        (
            "desconto de 10% em R$ 1.200,00",
            "1.200 com 10% de desconto fica 1.080 (desconto de 120).",
        ),
        ("230 mais 10%", "230 mais 10% fica 253 (aumento de 23)."),
        ("30 é quantos por cento de 120", "30 é 25% de 120."),
        ("quanto por cento é 1 de 3", "1 é 33,3% de 3."),
        ("dividir 350 entre 4 pessoas", "350 dividido por 4 dá 87,50 para cada um."),
        ("quanto é 3 x 45,90", "Dá 137,70."),
        ("quanto é 1200 dividido por 12", "Dá 100."),
        ("calcula (2+3)*4", "Dá 20."),
        ("12*7", "Dá 84."),
        ("quanto é 2 elevado a 10", "Dá 1.024."),
        (
            "quantos dias faltam para o natal?",
            "Faltam 30 dias para sexta-feira, 25 de dezembro de 2026.",
        ),
        (
            "quantos dias faltam pra 25/11",
            "É hoje: quarta-feira, 25 de novembro de 2026.",
        ),
        (
            "quantos dias faltam para 10 de janeiro",
            "Faltam 46 dias para domingo, 10 de janeiro de 2027.",
        ),
        (
            "quantos dias entre 01/12 e 15/12",
            "São 14 dias entre 01/12/2026 e 15/12/2026.",
        ),
        ("que dia cai daqui a 45 dias", "Vai ser sábado, 9 de janeiro de 2027."),
        ("que dia foi há 30 dias", "Foi segunda-feira, 26 de outubro de 2026."),
        (
            "qual é a data daqui a 3 semanas",
            "Vai ser quarta-feira, 16 de dezembro de 2026.",
        ),
    ],
)
def test_responde(frase, resposta):
    assert calculos.responder(frase, AGORA) == resposta


@pytest.mark.parametrize(
    "frase",
    [
        "quanto custa um iphone 15",
        "que horas são",
        "abre o 7zip",
        "me lembra daqui a 10 minutos",
        "quanto é 10/0",
        "eu tenho 2 gatos",
        "2026",
        "quanto é 9^999999",
        "__import__('os').system('dir')",
        "quanto é 2 + abc",
    ],
)
def test_nao_e_calculo(frase):
    assert calculos.responder(frase, AGORA) is None


def test_vira_acao_rapida_de_leitura():
    from nicx.historico.autonomia import risco_acao

    action = intencoes.parse("quanto é 15% de 230")
    assert action is not None and action.kind == "calc"
    assert action.target == "15% de 230 é 34,50."
    assert risco_acao("calc") == "leitura"
    # Lembrete com número continua sendo lembrete.
    lembrete = intencoes.parse("me lembra daqui a 10 minutos de tirar o bolo")
    assert lembrete is not None and lembrete.kind == "remind"
