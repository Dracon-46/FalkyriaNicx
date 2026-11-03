# ruff: noqa: E501  (tabelas de padrões: um por linha fica mais legível)
"""'toda segunda às 9h', 'de segunda a sexta às 7h30', 'every weekday at 8 am'.

Recebe o texto já normalizado (minúsculas, sem acento). Devolve
``Agenda(dias, "HH:MM")`` ou None. Português, inglês, espanhol e francês.
"""

from __future__ import annotations

import re
from typing import Optional

from nicx.rotinas.modelo import DIAS, Agenda

_NOMES = {
    # português
    "segunda": "seg", "segundas": "seg", "terca": "ter", "tercas": "ter", "quarta": "qua", "quartas": "qua",
    "quinta": "qui", "quintas": "qui", "sexta": "sex", "sextas": "sex", "sabado": "sab", "sabados": "sab",
    "domingo": "dom", "domingos": "dom",
    # inglês
    "monday": "seg", "mondays": "seg", "tuesday": "ter", "tuesdays": "ter", "wednesday": "qua", "wednesdays": "qua",
    "thursday": "qui", "thursdays": "qui", "friday": "sex", "fridays": "sex", "saturday": "sab", "saturdays": "sab",
    "sunday": "dom", "sundays": "dom",
    # espanhol
    "lunes": "seg", "martes": "ter", "miercoles": "qua", "jueves": "qui", "viernes": "sex",
    # francês
    "lundi": "seg", "mardi": "ter", "mercredi": "qua", "jeudi": "qui", "vendredi": "sex", "samedi": "sab", "dimanche": "dom",
}  # fmt: skip
_TODOS = r"(?:todo dia|todos os dias|diariamente|every day|everyday|daily|todos los dias|cada dia|tous les jours|chaque jour)"
_UTEIS = (
    r"(?:dias uteis|nos dias uteis|durante a semana|de segunda a sexta|weekdays|every weekday|on weekdays"
    r"|dias laborables|de lunes a viernes|en semaine|du lundi au vendredi)"
)
_FIM = (
    r"(?:fim de semana|fins de semana|no fim de semana|nos fins de semana|weekends|on weekends|every weekend"
    r"|fines de semana|el fin de semana|le week end|le weekend)"
)
_PREFIXOS = r"(?:todas? (?:as |os )?|toda |todo |every |on |cada |tous les |todos los |los |le |les )?"
_HORA = re.compile(
    r"(?:as|a|at|a las|las|a la|vers)?\s*(?P<h>[01]?\d|2[0-3])(?:\s*(?:h|:)\s*(?P<m>[0-5]\d)?)?"
    r"\s*(?P<per>am|pm|da manha|da tarde|da noite|de la manana|de la tarde|de la noche|du matin|du soir|de l apres midi)?\s*(?:h|horas?|hours?)?$"
)


def _hora(texto: str) -> Optional[str]:
    m = _HORA.fullmatch(texto.strip())
    if not m:
        return None
    hora, minuto = int(m.group("h")), int(m.group("m") or 0)
    periodo = m.group("per") or ""
    if (
        periodo
        in {
            "pm",
            "da tarde",
            "da noite",
            "de la tarde",
            "de la noche",
            "du soir",
            "de l apres midi",
        }
        and hora < 12
    ):
        hora += 12
    if periodo == "am" and hora == 12:
        hora = 0
    return f"{hora:02d}:{minuto:02d}"


def _dias(texto: str) -> Optional[list[str]]:
    texto = texto.strip()
    if re.fullmatch(_TODOS, texto):
        return list(DIAS)
    if re.fullmatch(_UTEIS, texto):
        return list(DIAS[:5])
    if re.fullmatch(_FIM, texto):
        return ["sab", "dom"]
    m = re.fullmatch(r"(?:de|from|du) (\w+) (?:a|to|au|until) (\w+)", texto)
    if m and m.group(1) in _NOMES and m.group(2) in _NOMES:
        i, j = DIAS.index(_NOMES[m.group(1)]), DIAS.index(_NOMES[m.group(2)])
        return list(DIAS[i : j + 1]) if i <= j else list(DIAS[i:] + DIAS[: j + 1])
    texto = re.sub("^" + _PREFIXOS, "", texto)
    partes = [p for p in re.split(r"\s*(?:,| e | and | y | et )\s*", texto) if p]
    escolhidos = []
    for p in partes:
        p = (
            re.sub("^" + _PREFIXOS, "", p)
            .removesuffix("-feira")
            .replace(" feira", "")
            .strip()
        )
        if p not in _NOMES:
            return None
        escolhidos.append(_NOMES[p])
    pedidos = set(escolhidos)
    return [d for d in DIAS if d in pedidos] or None


def interpretar(texto: str) -> Optional[Agenda]:
    """'toda segunda e quarta as 18h' -> Agenda(['seg', 'qua'], '18:00')."""
    texto = " ".join(texto.replace("-", " ").split())
    # a hora é o primeiro número (com ou sem "às"/"at" antes); o resto são os dias
    m = re.search(r"\s(?:(?:as|a las|a la|at|vers|a)\s+)?(?=\d)(?P<hora>\d.*)$", texto)
    if not m:
        return None
    dias, hora = _dias(texto[: m.start()]), _hora(m.group("hora"))
    if not dias or not hora:
        return None
    return Agenda(dias=dias, hora=hora)


__all__ = ["interpretar"]
