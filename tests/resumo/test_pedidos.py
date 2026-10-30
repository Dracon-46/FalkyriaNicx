"""Pedidos do resumo (pt, en, es, fr) viram ação rápida, sem modelo."""

from __future__ import annotations

from datetime import datetime

import pytest

from nicx.acoes import agenda, handle, parse
from nicx.resumo import montagem

NOW = datetime(2026, 10, 30, 18, 30)


@pytest.mark.parametrize(
    ("frase", "op", "target"),
    [
        # Português
        ("resumo do dia", "hoje", ""),
        ("Resumo do dia!", "hoje", ""),
        ("Nicx, me dá o resumo do dia", "hoje", ""),
        ("faz um resumo do meu dia", "hoje", ""),
        ("como foi meu dia?", "hoje", ""),
        ("Como foi o meu dia hoje?", "hoje", ""),
        ("o que eu fiz hoje?", "hoje", ""),
        ("o que ficou pendente hoje?", "hoje", "pendente"),
        ("O que ficou pendente?", "hoje", "pendente"),
        ("quais são as minhas pendências de hoje", "hoje", "pendente"),
        ("resumo de ontem", "ontem", ""),
        ("me dá o resumo do dia de ontem", "ontem", ""),
        ("como foi meu dia ontem?", "ontem", ""),
        ("o que eu fiz ontem?", "ontem", ""),
        ("o que ficou pendente ontem?", "ontem", "pendente"),
        # Inglês
        ("Give me my daily summary", "hoje", ""),
        ("daily recap", "hoje", ""),
        ("How was my day?", "hoje", ""),
        ("What did I do today?", "hoje", ""),
        ("What's still pending today?", "hoje", "pendente"),
        ("what's left to do today", "hoje", "pendente"),
        ("yesterday's summary", "ontem", ""),
        ("What did I do yesterday?", "ontem", ""),
        # Espanhol
        ("¿Cómo fue mi día?", "hoje", ""),
        ("dame el resumen del día", "hoje", ""),
        ("¿Qué hice hoy?", "hoje", ""),
        ("¿Qué quedó pendiente hoy?", "hoje", "pendente"),
        ("resumen de ayer", "ontem", ""),
        ("¿Qué hice ayer?", "ontem", ""),
        # Francês
        ("Comment s'est passée ma journée ?", "hoje", ""),
        ("Donne-moi le résumé de la journée", "hoje", ""),
        ("Qu'est-ce que j'ai fait aujourd'hui ?", "hoje", ""),
        ("Qu'est-ce qui reste à faire aujourd'hui ?", "hoje", "pendente"),
        ("résumé d'hier", "ontem", ""),
        ("Qu'est-ce que j'ai fait hier ?", "ontem", ""),
    ],
)
def test_pedidos(frase, op, target):
    action = parse(frase)
    assert action is not None, frase
    assert (action.kind, action.op, action.target) == ("resumo", op, target)


@pytest.mark.parametrize(
    "frase",
    [
        "resume o que eu copiei",
        "o que eu tenho hoje",
        "me fala um resumo do livro",
        "how was the movie",
        "minhas pendências",
        "como foi o jogo ontem",
        "o que é um resumo do dia na escola?",
    ],
)
def test_nao_sao_pedidos_de_resumo(frase):
    action = parse(frase)
    assert action is None or action.kind != "resumo"


@pytest.fixture
def agora_fixo(monkeypatch):
    monkeypatch.setattr(montagem, "agora_local", lambda: NOW)


def test_responde_na_hora(agora_fixo):
    agenda.add("dentista", datetime(2026, 10, 31, 9, 0), now=datetime(2026, 10, 1))
    outcome = handle("resumo do dia")
    assert outcome is not None and outcome.ok
    assert outcome.message.startswith("Resumo do seu dia.")
    assert outcome.message.endswith("Amanhã você tem: dentista às 9h.")


def test_responde_no_idioma_da_interface(agora_fixo):
    assert handle("What did I do today?", "en").message.startswith(
        "Summary of your day."
    )
    assert handle("¿Qué hice ayer?", "es").message.startswith("Resumen de ayer.")
    assert handle("o que ficou pendente hoje?", "fr").message.startswith(
        "Rien n'est en attente aujourd'hui."
    )


def test_resumo_de_ontem(agora_fixo):
    assert handle("resumo de ontem").message.startswith("Resumo de ontem.")
