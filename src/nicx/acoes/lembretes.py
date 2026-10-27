"""Lembretes e timers: guardados em ~/.nicx/lembretes.json, disparados pelo servidor.

O despertador (``start_alarm``) roda numa thread do ``nicx serve``. Quando um
lembrete vence, o Nicx mostra uma notificação do Windows e, se a voz local
estiver instalada, fala o lembrete. Lembretes que venceram com o servidor
desligado disparam assim que ele voltar, avisando que estão atrasados.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_ALARM: Optional[threading.Thread] = None
_STOP = threading.Event()
# Atraso a partir do qual o aviso diz que o lembrete passou da hora.
_LATE = timedelta(minutes=2)


@dataclass
class Reminder:
    id: str
    text: str
    due: str  # ISO, hora local
    created: str

    @property
    def due_at(self) -> datetime:
        return datetime.fromisoformat(self.due)


def _path() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "lembretes.json"


def _load() -> List[Reminder]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Reminder(**item) for item in raw]
    except (ValueError, TypeError) as exc:
        logger.warning("lembretes.json ilegível (%s); começando vazio", exc)
        return []


def _save(items: List[Reminder]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([asdict(r) for r in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def add(text: str, when: datetime) -> Reminder:
    reminder = Reminder(
        id=uuid.uuid4().hex[:8],
        text=text.strip() or "o que você pediu",
        due=when.replace(microsecond=0).isoformat(),
        created=datetime.now().replace(microsecond=0).isoformat(),
    )
    with _LOCK:
        items = _load()
        items.append(reminder)
        _save(items)
    return reminder


def pending() -> List[Reminder]:
    with _LOCK:
        return sorted(_load(), key=lambda r: r.due)


def cancel_all() -> int:
    with _LOCK:
        count = len(_load())
        _save([])
    return count


def pop_due(now: Optional[datetime] = None) -> List[Reminder]:
    """Tira da lista e devolve os lembretes vencidos."""
    now = now or datetime.now()
    with _LOCK:
        items = _load()
        due = [r for r in items if r.due_at <= now]
        if due:
            _save([r for r in items if r.due_at > now])
    return due


def message_for(reminder: Reminder, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    text = f"Lembrete: {reminder.text}."
    if now - reminder.due_at > _LATE:
        text += f" (era para {reminder.due_at:%H:%M}; o Nicx estava desligado)"
    return text


# ---------------------------------------------------------------------------
# Aviso: notificação do Windows + voz
# ---------------------------------------------------------------------------

# AUMID do PowerShell: o Windows só mostra toasts de apps registrados.
_PS_APP_ID = (
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
)
_TOAST_SCRIPT = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
    " ContentType = WindowsRuntime] > $null;"
    "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
    "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
    "$x = $t.GetElementsByTagName('text');"
    "$x.Item(0).AppendChild($t.CreateTextNode('Nicx')) > $null;"
    "$x.Item(1).AppendChild($t.CreateTextNode($env:NICX_AVISO)) > $null;"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
    "$env:NICX_APP_ID).Show([Windows.UI.Notifications.ToastNotification]::new($t))"
)


def show_notification(message: str) -> None:
    """Notificação do sistema. O texto vai por variável de ambiente (sem escapes)."""
    try:
        if sys.platform == "win32":
            env = {**os.environ, "NICX_AVISO": message, "NICX_APP_ID": _PS_APP_ID}
            subprocess.run(  # noqa: S603
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _TOAST_SCRIPT,
                ],
                env=env,
                capture_output=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        elif sys.platform == "darwin":
            subprocess.run(  # noqa: S603, S607
                [
                    "osascript",
                    "-e",
                    f'display notification {json.dumps(message)} with title "Nicx"',
                ],
                capture_output=True,
                timeout=20,
            )
        else:
            subprocess.run(
                ["notify-send", "Nicx", message], capture_output=True, timeout=20
            )  # noqa: S603, S607
    except Exception as exc:  # noqa: BLE001 - aviso é melhor esforço
        logger.info("Notificação não exibida: %s", exc)


def speak(message: str) -> None:
    """Fala o aviso com a voz local, se instalada. Silencioso se não houver."""
    try:
        import io

        import sounddevice as sd
        import soundfile as sf

        from nicx.nucleo.config import load_config
        from nicx.voz._tts_discovery import get_tts_backend

        speech = load_config().speech
        backend = get_tts_backend(getattr(speech, "tts_backend", "kokoro"))
        if backend is None:
            return
        result = backend.synthesize(
            message,
            voice_id=getattr(speech, "voice_id", "") or "pf_dora",
            speed=getattr(speech, "voice_speed", 1.0) or 1.0,
            output_format="wav",
        )
        data, rate = sf.read(io.BytesIO(result.audio), dtype="float32")
        sd.play(data, rate)
        sd.wait()
    except Exception as exc:  # noqa: BLE001 - sem voz, fica só a notificação
        logger.info("Aviso falado indisponível: %s", exc)


def notify(reminder: Reminder) -> None:
    message = message_for(reminder)
    logger.info("Disparando %s", message)
    show_notification(message)
    speak(message)


def _loop(interval: float, on_due: Callable[[Reminder], None]) -> None:
    while not _STOP.wait(interval):
        try:
            for reminder in pop_due():
                on_due(reminder)
        except Exception:  # noqa: BLE001 - o despertador nunca pode morrer
            logger.exception("Falha no despertador de lembretes")


def start_alarm(
    interval: float = 10.0, on_due: Callable[[Reminder], None] = notify
) -> threading.Thread:
    """Liga o despertador (uma vez por processo)."""
    global _ALARM
    if _ALARM is not None and _ALARM.is_alive():
        return _ALARM
    _STOP.clear()
    _ALARM = threading.Thread(
        target=_loop, args=(interval, on_due), name="despertador", daemon=True
    )
    _ALARM.start()
    return _ALARM


def stop_alarm() -> None:
    _STOP.set()
