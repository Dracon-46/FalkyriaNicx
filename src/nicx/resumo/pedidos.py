"""Pedidos do resumo do dia em português, inglês, espanhol e francês.

"resumo do dia", "como foi meu dia?", "o que eu fiz hoje?", "o que ficou
pendente hoje?", "resumo de ontem" (e o mesmo nos outros três idiomas).
O texto chega limpo por ``nicx.acoes.intencoes.clean_with_map``: minúsculas,
sem acento e sem pontuação ("what's" vira "what s"; hífens ficam).

Devolve uma ``Action("resumo")``: ``op`` é "hoje" ou "ontem" e ``target``
"pendente" quando o pedido é só pelo que ficou para depois.
"""

from __future__ import annotations

import re
from typing import Optional

from nicx.acoes.intencoes import Action

# Gentilezas em volta do pedido, nos quatro idiomas.
_ANTES = re.compile(
    r"^(?:(?:hey|hi|ok|oye|hola|salut|dis)\s+)?(?:nicx\s+)?"
    r"(?:(?:please|por favor|s il te plait|s il vous plait)\s+)?"
)
_DEPOIS = re.compile(
    r"(?:\s+(?:please|por favor|s il te plait|s il vous plait|nicx))+$"
)

# --- Português --------------------------------------------------------------
_PT_PEDIR = (
    r"(?:(?:me )?(?:da|de|faz|faca|fala|mostra|manda|le|quero|qual e|qual)"
    r"(?: (?:o|um|meu))? )?"
)
_PT_DIA = r"(?: (?P<d>hoje|ontem|de hoje|de ontem))?"
_PT = [
    (
        _PT_PEDIR
        + r"resumo (?:do (?:meu )?dia|diario|de hoje)(?P<o> de ontem)?(?: de hoje)?",
        "",
    ),
    (_PT_PEDIR + r"resumo de ontem", "ontem"),
    (r"como (?:foi|ta sendo|esta sendo) (?:o )?(?:meu )?dia" + _PT_DIA, ""),
    (r"como foi (?P<d>hoje|ontem)", ""),
    (r"o que (?:eu )?fiz (?:(?:no|durante o) dia )?(?P<d>hoje|ontem)", ""),
]
_PT_PENDENTE = [
    r"o que (?:ainda )?(?:ficou|esta|ta|tem|ta faltando|esta faltando) pendente"
    + _PT_DIA,
    r"(?:o que )?(?:ainda )?falta (?:fazer )?(?P<d>hoje)",
    r"(?:quais (?:sao )?)?(?:as )?(?:minhas )?pendencias"
    r" (?P<d>de hoje|de ontem|do dia)",
    r"o que (?:eu )?deixei (?:pendente|pra depois|para depois)" + _PT_DIA,
]

# --- Inglês -----------------------------------------------------------------
_EN_PEDIR = r"(?:(?:give me|show me|tell me|read me|what s|what is) )?(?:my |a |the )?"
_EN = [
    (
        _EN_PEDIR + r"(?:daily summary|daily recap|day summary|end of day summary|"
        r"summary of (?:my |the )?day|recap of (?:my |the )?day|"
        r"today s (?:summary|recap)|summary (?:of|for) today|recap (?:of|for) today)",
        "hoje",
    ),
    (
        _EN_PEDIR
        + r"(?:yesterday s (?:summary|recap)|(?:summary|recap) (?:of|for) yesterday)",
        "ontem",
    ),
    (r"how (?:was|did) my day(?: go)?(?: (?P<d>today|yesterday))?", ""),
    (r"how was (?P<d>today|yesterday)", ""),
    (r"what did i do (?P<d>today|yesterday)", ""),
]
_EN_PENDENTE = [
    r"what s (?:still )?(?:pending|left(?: to do)?)(?: (?:for )?(?P<d>today))?",
    r"what is (?:still )?(?:pending|left(?: to do)?)(?: (?:for )?(?P<d>today))?",
    r"what did i leave (?:pending|undone|unfinished)(?: (?P<d>today|yesterday))?",
    r"what (?:was|got) left (?:pending|undone)(?: (?P<d>today|yesterday))?",
]

# --- Espanhol ---------------------------------------------------------------
_ES_PEDIR = r"(?:(?:dame|hazme|muestrame|quiero|cual es) )?(?:el |un |mi )?"
_ES = [
    (
        _ES_PEDIR + r"resumen (?:del dia|de mi dia|diario|de hoy)(?P<o> de ayer)?",
        "",
    ),
    (_ES_PEDIR + r"resumen de ayer", "ontem"),
    (r"como (?:fue|ha sido|va) mi dia(?: (?P<d>hoy|ayer))?", ""),
    (r"como me (?:fue|ha ido) (?P<d>hoy|ayer)", ""),
    (r"como fue (?P<d>hoy|ayer)", ""),
    (r"que hice (?P<d>hoy|ayer)", ""),
]
_ES_PENDIENTE = [
    r"que (?:me )?(?:quedo|queda|esta|sigue) pendiente"
    r"(?: (?P<d>hoy|de hoy|ayer|de ayer))?",
    r"que me (?:falta|queda) (?:por )?(?:hacer )?(?P<d>hoy)",
    r"(?:cuales son )?mis pendientes (?P<d>de hoy|de ayer)",
]

# --- Francês ----------------------------------------------------------------
_FR_PEDIR = (
    r"(?:(?:donne[- ]moi|fais[- ]moi|montre[- ]moi|lis[- ]moi) )?(?:le |un |mon )?"
)
_FR = [
    (
        _FR_PEDIR
        + r"(?:resume|bilan|recapitulatif|recap) (?:de (?:la|ma) journee|du jour|"
        r"quotidien|d aujourd hui)(?P<o> d hier)?",
        "",
    ),
    (_FR_PEDIR + r"(?:resume|bilan|recapitulatif|recap) d hier", "ontem"),
    (
        r"comment (?:s est passee|s est deroulee|etait|a ete) ma journee"
        r"(?: (?P<d>aujourd hui|d hier))?",
        "",
    ),
    (r"comment (?:c etait|ca s est passe) (?P<d>aujourd hui|hier)", ""),
    (r"qu est[- ]ce que j ai fait (?P<d>aujourd hui|hier)", ""),
    (r"qu ai[- ]je fait (?P<d>aujourd hui|hier)", ""),
]
_FR_PENDENTE = [
    r"qu est[- ]ce qui (?:reste|est (?:reste )?en attente|est reste en suspens)"
    r"(?: a faire)?(?: (?P<d>aujourd hui|d hier))?",
    r"qu est[- ]ce qu il (?:me )?reste a faire(?: (?P<d>aujourd hui))?",
    r"(?:quelles sont )?mes taches en attente (?P<d>d aujourd hui|d hier)",
]

_ONTEM = {"ontem", "de ontem", "yesterday", "ayer", "de ayer", "hier", "d hier"}


def _dia(m: re.Match[str], padrao: str) -> str:
    if padrao:
        return padrao
    grupos = m.groupdict()
    if grupos.get("o"):
        return "ontem"
    d = grupos.get("d") or ""
    return "ontem" if d in _ONTEM else "hoje"


def _limpar(t: str) -> str:
    t = _ANTES.sub("", t, count=1)
    return _DEPOIS.sub("", t).strip()


def parse(t: str) -> Optional[Action]:
    """O pedido de resumo em ``t`` (texto já limpo), ou None."""
    t = _limpar(t)
    if not t or len(t) > 80:
        return None
    for padroes, pendentes in (
        (_PT, _PT_PENDENTE),
        (_EN, _EN_PENDENTE),
        (_ES, _ES_PENDIENTE),
        (_FR, _FR_PENDENTE),
    ):
        for padrao in pendentes:
            m = re.fullmatch(padrao, t)
            if m:
                return Action("resumo", op=_dia(m, ""), target="pendente")
        for padrao, dia in padroes:
            m = re.fullmatch(padrao, t)
            if m:
                return Action("resumo", op=_dia(m, dia))
    return None


__all__ = ["parse"]
