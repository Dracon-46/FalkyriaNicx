"""Entende quando, em português: "em 20 minutos", "às 3 da tarde", "amanhã às 8".

Recebe texto já normalizado (minúsculas, sem acento; ver ``intencoes.normalize``)
e devolve um ``datetime`` no fuso local. Nada aqui toca no sistema.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

_UNITS = {
    "zero": 0,
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "catorze": 14,
    "quatorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezessete": 17,
    "dezoito": 18,
    "dezenove": 19,
}
_TENS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60}

# Um número escrito com algarismos ou por extenso até 69 ("vinte e cinco").
NUMBER = (
    r"(?:\d{1,3}|(?:" + "|".join(_TENS) + r")(?: e (?:" + "|".join(_UNITS) + r"))?"
    r"|" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")"
)


def to_number(text: str) -> Optional[int]:
    """'25', 'vinte e cinco', 'cinco' -> int; None se não for número."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text in _UNITS:
        return _UNITS[text]
    parts = text.split(" e ")
    if parts[0] in _TENS:
        total = _TENS[parts[0]]
        if len(parts) == 2:
            if parts[1] not in _UNITS:
                return None
            total += _UNITS[parts[1]]
        return total
    return None


_UNIT_SECONDS = {
    "segundo": 1,
    "segundos": 1,
    "seg": 1,
    "minuto": 60,
    "minutos": 60,
    "min": 60,
    "hora": 3600,
    "horas": 3600,
    "h": 3600,
    "dia": 86400,
    "dias": 86400,
}
_DURATION = re.compile(
    rf"(?P<n>{NUMBER}|meia) (?P<u>segundos?|seg|minutos?|min|horas?|h|dias?)"
    r"(?: e (?P<n2>" + NUMBER + r"|meia) (?P<u2>segundos?|minutos?|horas?))?"
)


def parse_duration(text: str) -> Optional[timedelta]:
    """'10 minutos', 'meia hora', 'uma hora e meia', '2 horas e 15 minutos'."""
    text = text.strip()
    if text in ("meia hora",):
        return timedelta(minutes=30)
    m = re.fullmatch(r"(?P<h>" + NUMBER + r") horas? e meia", text)
    if m and to_number(m.group("h")) is not None:
        return timedelta(hours=to_number(m.group("h")), minutes=30)
    m = _DURATION.fullmatch(text)
    if not m:
        return None
    total = 0.0
    for n_key, u_key in (("n", "u"), ("n2", "u2")):
        n_raw, unit = m.group(n_key), m.group(u_key)
        if n_raw is None:
            continue
        n = 0.5 if n_raw == "meia" else to_number(n_raw)
        if n is None:
            return None
        total += n * _UNIT_SECONDS[unit]
    return timedelta(seconds=total) if total > 0 else None


_PERIODS = {
    "da manha": "manha",
    "da tarde": "tarde",
    "da noite": "noite",
    "da madrugada": "madrugada",
}
_CLOCK = re.compile(
    r"(?:(?P<day>hoje|amanha|depois de amanha) )?"
    r"(?:as |a |ao |para as |pras |pra )?"
    r"(?:(?P<noon>meio dia|meio-dia|meia noite|meia-noite)"
    r"|(?P<h>" + NUMBER + r")(?:(?::| e |h ?)(?P<m>\d{1,2}|" + NUMBER + r"|meia))?"
    r"(?: ?(?:horas?|h))?(?P<per> da manha| da tarde| da noite| da madrugada)?)"
    r"(?: (?P<day2>de hoje|de amanha|amanha|hoje))?"
)


def parse_clock(
    text: str, now: Optional[datetime] = None, *, morning: bool = False
) -> Optional[datetime]:
    """'às 15h30', 'às 3 da tarde', 'amanhã às 8', 'meio-dia'. Próxima ocorrência.

    Sem "da manhã/tarde/noite", de 1 a 6 horas é à tarde ("às 3" = 15h), como
    se fala no dia a dia; ``morning=True`` (alarmes) mantém de madrugada.
    """
    now = now or datetime.now()
    m = _CLOCK.fullmatch(text.strip())
    if not m:
        return None
    if m.group("noon"):
        hour, minute = (12, 0) if m.group("noon").startswith("meio") else (0, 0)
    else:
        hour = to_number(m.group("h"))
        raw_min = m.group("m")
        if raw_min is None:
            minute = 0
        elif raw_min == "meia":
            minute = 30
        else:
            minute = to_number(raw_min)
        if hour is None or minute is None:
            return None
        period = (m.group("per") or "").strip()
        if period in ("da tarde", "da noite") and hour < 12:
            hour += 12
        elif period in ("da noite", "da manha", "da madrugada") and hour == 12:
            hour = 0  # "12 da noite" é meia-noite
        elif not period and not morning and 1 <= hour <= 6 and minute <= 59:
            hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    day = m.group("day") or (m.group("day2") or "").replace("de ", "")
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if day == "amanha":
        target += timedelta(days=1)
    elif day == "depois de amanha":
        target += timedelta(days=2)
    elif target <= now:
        # "às 8" depois das 8 vira 20h; alarme "às 6" depois das 6 é amanhã cedo.
        if (
            not morning
            and not m.group("per")
            and not m.group("noon")
            and hour < 12
            and target + timedelta(hours=12) > now
        ):
            target += timedelta(hours=12)
        else:
            target += timedelta(days=1)
    return target


def parse_when(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'em 10 minutos', 'daqui a meia hora', 'às 15h', 'amanhã às 8'."""
    now = now or datetime.now()
    text = text.strip()
    m = re.fullmatch(r"(?:em|daqui a|daqui|dentro de|por) (?P<d>.+)", text)
    if m:
        duration = parse_duration(m.group("d"))
        return now + duration if duration else None
    return parse_clock(text, now)


def say_when(when: datetime, now: Optional[datetime] = None) -> str:
    """Hora do lembrete do jeito que se fala: 'às 15h30', 'amanhã às 8h'."""
    now = now or datetime.now()
    hhmm = f"{when.hour}h" if when.minute == 0 else f"{when.hour}h{when.minute:02d}"
    # Perto: em minutos, mesmo virando o dia (timer às 23h57 = "em 5 minutos").
    delta = when - now
    if delta < timedelta(minutes=1):
        secs = max(1, round(delta.total_seconds()))
        return f"em {secs} segundo{'s' if secs > 1 else ''}"
    if delta < timedelta(hours=1):
        mins = max(1, round(delta.total_seconds() / 60))
        return f"em {mins} minuto{'s' if mins > 1 else ''}"
    days = (when.date() - now.date()).days
    if days == 0:
        return f"às {hhmm}"
    if days == 1:
        return f"amanhã às {hhmm}"
    return f"dia {when.day:02d}/{when.month:02d} às {hhmm}"


# ---------------------------------------------------------------------------
# Dias: "sexta", "amanhã", "dia 30", "30/10", "5 de novembro" (para a agenda)
# ---------------------------------------------------------------------------

_WEEKDAYS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}
WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
_MONTHS = {
    name: i + 1
    for i, name in enumerate(
        (
            "janeiro",
            "fevereiro",
            "marco",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        )
    )
}
_DAY = re.compile(
    r"(?:(?:para|pra|no|na|em) )?"
    r"(?:(?P<rel>hoje|amanha|depois de amanha)"
    r"|(?:(?:nesta|neste|nessa|nesse|esta|este|essa|esse|na|no) )?"
    r"(?P<next>(?:proxima|proximo) )?(?P<wd>" + "|".join(_WEEKDAYS) + r")"
    r"(?:[ -]feira)?(?P<later> que vem)?"
    r"|(?:dia )?(?P<d>\d{1,2})-(?P<m>\d{1,2})(?:-(?P<y>\d{2,4}))?"
    r"|(?:(?:no )?dia )?(?P<dn>"
    + NUMBER
    + r")(?: de (?P<mon>"
    + "|".join(_MONTHS)
    + r"))"
    r"|(?:no )?dia (?P<dd>" + NUMBER + r"))"
)


def parse_day(text: str, now: Optional[datetime] = None) -> Optional[date]:
    """'amanha', 'sexta', 'dia 30', '30-10' (já normalizado), '5 de novembro'.

    Sem ano, uma data que já passou é a do ano (ou mês) seguinte.
    """
    now = now or datetime.now()
    today = now.date()
    m = _DAY.fullmatch(text.strip())
    if not m:
        return None
    if m.group("rel"):
        offset = {"hoje": 0, "amanha": 1, "depois de amanha": 2}[m.group("rel")]
        return today + timedelta(days=offset)
    if m.group("wd"):
        delta = (_WEEKDAYS[m.group("wd")] - today.weekday()) % 7
        if delta == 0 and (m.group("next") or m.group("later")):
            delta = 7
        return today + timedelta(days=delta)
    try:
        if m.group("d"):
            day, month = int(m.group("d")), int(m.group("m"))
            year = int(m.group("y")) if m.group("y") else today.year
            year += 2000 if year < 100 else 0
            found = date(year, month, day)
            if not m.group("y") and found < today:
                found = date(year + 1, month, day)
            return found
        if m.group("dn"):
            day = to_number(m.group("dn"))
            month = _MONTHS[m.group("mon")]
            if day is None:
                return None
            found = date(today.year, month, day)
            return found if found >= today else date(today.year + 1, month, day)
        day = to_number(m.group("dd") or "")
        if day is None:
            return None
        found = date(today.year, today.month, day)
        if found < today:
            month = today.month % 12 + 1
            found = date(today.year + (month == 1), month, day)
        return found
    except ValueError:
        return None  # 31/02 e afins


def _clock_on(text: str, day: date) -> Optional[datetime]:
    """Horário ('às 15h', '3 da tarde') naquele dia."""
    start = datetime.combine(day, datetime.min.time())
    when = parse_clock(text, start)
    if when is None or when.date() != day:
        return None
    return when


def parse_moment(
    text: str, now: Optional[datetime] = None
) -> Optional[tuple[datetime, bool]]:
    """Dia e hora para a agenda: 'sexta às 15h', 'amanhã', 'às 10 do dia 30'.

    Devolve ``(início, tem_hora)``; sem hora, é um compromisso do dia todo.
    """
    now = now or datetime.now()
    text = re.sub(r"^(?:para|pra|marcado para) ", "", text.strip())
    day = parse_day(text, now)
    if day is not None:
        return datetime.combine(day, datetime.min.time()), False
    words = text.split()
    for i in range(1, len(words)):
        left, right = " ".join(words[:i]), " ".join(words[i:])
        right = re.sub(r"^(?:do|no|de) (?=dia )", "", right)
        for day_text, clock_text in ((left, right), (right, left)):
            day = parse_day(day_text, now)
            if day is None:
                continue
            when = _clock_on(clock_text, day)
            if when is not None:
                return when, True
    when = parse_clock(text, now)
    return (when, True) if when is not None else None


def say_day(
    when: datetime, now: Optional[datetime] = None, *, with_time: bool = True
) -> str:
    """'hoje às 15h', 'amanhã', 'sexta (31/10) às 9h30'."""
    now = now or datetime.now()
    days = (when.date() - now.date()).days
    if days == 0:
        label = "hoje"
    elif days == 1:
        label = "amanhã"
    elif 1 < days < 7:
        label = f"{WEEKDAY_NAMES[when.weekday()]} ({when.day:02d}/{when.month:02d})"
    else:
        label = f"dia {when.day:02d}/{when.month:02d}"
    if not with_time:
        return label
    hhmm = f"{when.hour}h" if when.minute == 0 else f"{when.hour}h{when.minute:02d}"
    return f"{label} às {hhmm}"
