# ruff: noqa: E501  (tabelas de padrões: um por linha fica mais legível)
"""'até dezembro', 'até 15/12', 'em 3 meses', 'by december 15', 'dans 6 semaines'.

Recebe texto normalizado (minúsculas, sem acento). Devolve a data limite ou None.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Optional

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "enero": 1, "febrero": 2, "abril_es": 4, "mayo": 5, "junio": 6, "julio": 7, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre_fr": 11, "decembre": 12,
}  # fmt: skip
_UNIDADES = {
    "dia": 1, "dias": 1, "day": 1, "days": 1, "jour": 1, "jours": 1,
    "semana": 7, "semanas": 7, "week": 7, "weeks": 7, "semaine": 7, "semaines": 7,
    "mes": 30, "meses": 30, "month": 30, "months": 30, "mois": 30,
    "ano": 365, "anos": 365, "year": 365, "years": 365, "ano_es": 365, "an": 365, "ans": 365,
}  # fmt: skip
_NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
    "nove": 9, "dez": 10, "doze": 12, "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "eight": 8, "ten": 10, "twelve": 12, "un": 1, "una": 1, "dos": 2, "deux": 2, "trois": 3,
    "cuatro": 4, "quatre": 4, "seis_es": 6, "six_fr": 6,
}  # fmt: skip
_PREP = r"(?:ate|em|daqui a|dentro de|by|until|in|within|before|hasta|en|antes de|dentro de|d ici|avant|dans|en)"


def _fim_do_mes(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def _no_futuro(alvo: date, hoje: date) -> date:
    return alvo if alvo > hoje else alvo.replace(year=alvo.year + 1)


def interpretar(texto: str, hoje: Optional[date] = None) -> Optional[date]:
    hoje = hoje or date.today()
    t = " ".join(texto.replace("-", " ").replace("/", " / ").split())
    t = re.sub(
        rf"^{_PREP}\s+(?:o |a |the |el |le |la |fin de |fim de |the end of |end of )?",
        "",
        t,
    )
    if t in {
        "fim do ano",
        "o fim do ano",
        "final do ano",
        "end of the year",
        "the end of the year",
        "fin de ano",
        "fin de l annee",
        "fim de ano",
    }:
        return date(hoje.year, 12, 31)
    m = re.fullmatch(r"(?P<n>\d{1,3}|\w+)\s+(?P<u>\w+)", t)
    if m and m.group("u") in _UNIDADES:
        n = int(m.group("n")) if m.group("n").isdigit() else _NUMEROS.get(m.group("n"))
        if n:
            return hoje + timedelta(days=n * _UNIDADES[m.group("u")])
    m = re.fullmatch(
        r"(?P<d>\d{1,2})\s*/\s*(?P<m>\d{1,2})(?:\s*/\s*(?P<a>\d{2,4}))?", t
    )
    if m:
        ano = int(m.group("a")) if m.group("a") else hoje.year
        ano += 2000 if ano < 100 else 0
        try:
            alvo = date(ano, int(m.group("m")), int(m.group("d")))
        except ValueError:
            return None
        return alvo if m.group("a") else _no_futuro(alvo, hoje)
    m = re.fullmatch(
        r"(?:(?P<d>\d{1,2}) (?:de )?)?(?P<mes>[a-z]+)(?: (?P<d2>\d{1,2}))?(?: (?:de )?(?P<a>\d{4}))?",
        t,
    )
    if m:
        nome = m.group("mes")
        mes = _MESES.get(nome) or _MESES.get(f"{nome}_es") or _MESES.get(f"{nome}_fr")
        if not mes:
            return None
        ano = int(m.group("a")) if m.group("a") else hoje.year
        dia = m.group("d") or m.group("d2")
        try:
            alvo = date(ano, mes, int(dia)) if dia else _fim_do_mes(ano, mes)
        except ValueError:
            return None
        return alvo if m.group("a") else _no_futuro(alvo, hoje)
    return None


__all__ = ["interpretar"]
