"""Agenda do Nicx: compromissos guardados no PC, com aviso antes da hora.

"Marca reunião com o João sexta às 15h" vira um compromisso em
``~/.nicx/agenda.json`` e um lembrete 15 minutos antes (o despertador dos
lembretes avisa com notificação e voz). Compromisso sem hora é do dia todo
e avisa às 8h. ``exportar_ics`` gera um arquivo .ics que o calendário do
Windows (ou Outlook, Google Agenda...) importa com dois cliques.

Tudo local: nada vai para a internet.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from nicx.acoes import lembretes

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
WARN_BEFORE = timedelta(minutes=15)
ALL_DAY_WARN_HOUR = 8
DEFAULT_DURATION = timedelta(hours=1)


@dataclass
class Event:
    id: str
    title: str
    start: str  # ISO, hora local
    all_day: bool
    created: str
    reminder_id: str = ""

    @property
    def start_at(self) -> datetime:
        return datetime.fromisoformat(self.start)


def _path() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "agenda.json"


def _load() -> List[Event]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("não é uma lista")
    except (ValueError, TypeError) as exc:
        backup = path.with_suffix(".json.bak")
        os.replace(path, backup)
        logger.warning("agenda.json ilegível (%s); guardado em %s", exc, backup.name)
        return []
    events: List[Event] = []
    for item in raw:
        try:
            event = Event(**item)
            event.start_at  # data inválida (edição à mão) fica de fora
        except (TypeError, ValueError):
            logger.warning("Compromisso inválido ignorado: %r", item)
            continue
        events.append(event)
    return events


def _save(events: List[Event]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _warning_time(start: datetime, all_day: bool) -> datetime:
    if all_day:
        return start.replace(hour=ALL_DAY_WARN_HOUR, minute=0)
    return start - WARN_BEFORE


def add(
    title: str, start: datetime, all_day: bool = False, now: Optional[datetime] = None
) -> Event:
    """Marca um compromisso e o aviso antes dele (se ainda der tempo)."""
    now = now or datetime.now()
    title = title.strip() or "compromisso"
    event = Event(
        id=uuid.uuid4().hex[:8],
        title=title,
        start=start.replace(second=0, microsecond=0).isoformat(),
        all_day=all_day,
        created=now.isoformat(timespec="seconds"),
    )
    warn_at = _warning_time(event.start_at, all_day)
    if warn_at > now:
        prefix = "Hoje" if all_day else "Daqui a 15 minutos"
        event.reminder_id = lembretes.add(f"{prefix}: {title}", warn_at).id
    with _LOCK:
        events = _load()
        events.append(event)
        _save(events)
    return event


def upcoming(now: Optional[datetime] = None, days: int = 7) -> List[Event]:
    """Compromissos de agora até ``days`` dias à frente (e os de dia todo de hoje)."""
    now = now or datetime.now()
    end = datetime.combine(now.date() + timedelta(days=days), datetime.max.time())
    with _LOCK:
        events = _load()
    keep = [
        e
        for e in events
        if (
            e.start_at.date() >= now.date()
            if e.all_day
            else e.start_at >= now - DEFAULT_DURATION
        )
        and e.start_at <= end
    ]
    return sorted(keep, key=lambda e: e.start)


def on_day(day: date) -> List[Event]:
    with _LOCK:
        events = _load()
    return sorted(
        (e for e in events if e.start_at.date() == day), key=lambda e: e.start
    )


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


_STOPWORDS = {
    "o",
    "a",
    "os",
    "as",
    "de",
    "da",
    "do",
    "com",
    "e",
    "um",
    "uma",
    "meu",
    "minha",
}


def find(
    query: str, now: Optional[datetime] = None, day: Optional[date] = None
) -> Optional[Event]:
    """O próximo compromisso cujo título tem todas as palavras da busca
    (e que cai em ``day``, se dado)."""
    words = [w for w in _norm(query).split() if w not in _STOPWORDS]
    for event in upcoming(now, days=366):
        if day is not None and event.start_at.date() != day:
            continue
        title = _norm(event.title)
        if all(w in title for w in words):
            return event
    return None


def cancel(event: Event) -> None:
    """Desmarca o compromisso e o aviso dele."""
    with _LOCK:
        _save([e for e in _load() if e.id != event.id])
    if event.reminder_id:
        lembretes.cancel_id(event.reminder_id)


# ---------------------------------------------------------------------------
# Exportar para outros calendários (.ics)
# ---------------------------------------------------------------------------


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def to_ics(events: List[Event]) -> str:
    """Calendário iCalendar (RFC 5545) com os compromissos, em hora local."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Falkyria//Nicx//PT-BR",
        "CALSCALE:GREGORIAN",
    ]
    for e in events:
        start = e.start_at
        lines += ["BEGIN:VEVENT", f"UID:{e.id}@nicx.falkyria", f"DTSTAMP:{stamp}"]
        if e.all_day:
            lines += [
                f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
                f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}",
            ]
        else:
            lines += [
                f"DTSTART:{start:%Y%m%dT%H%M%S}",
                f"DTEND:{start + DEFAULT_DURATION:%Y%m%dT%H%M%S}",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_ics_text(e.title)}",
                "TRIGGER:-PT15M",
                "END:VALARM",
            ]
        lines += [f"SUMMARY:{_ics_text(e.title)}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def export_ics(events: List[Event]) -> Path:
    """Grava os compromissos num .ics (para abrir no calendário do Windows)."""
    from nicx.nucleo.paths import get_config_dir

    folder = get_config_dir() / "agenda"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"compromissos-{datetime.now():%Y%m%d-%H%M%S}.ics"
    path.write_text(to_ics(events), encoding="utf-8", newline="")
    return path


__all__ = [
    "Event",
    "add",
    "cancel",
    "export_ics",
    "find",
    "on_day",
    "to_ics",
    "upcoming",
]
