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
    # Idioma do pedido ("en", "es"...): o aviso sai nele. Arquivos antigos não
    # têm o campo e avisam em português.
    idioma: str = ""

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
        if not isinstance(raw, list):
            raise ValueError("não é uma lista")
    except (ValueError, TypeError) as exc:
        # Guarda o arquivo ruim em vez de sobrescrever no próximo lembrete.
        backup = path.with_suffix(".json.bak")
        os.replace(path, backup)
        logger.warning("lembretes.json ilegível (%s); guardado em %s", exc, backup.name)
        return []
    items: List[Reminder] = []
    for item in raw:
        try:
            reminder = Reminder(**item)
            reminder.due_at  # data inválida (edição à mão) fica de fora
        except (TypeError, ValueError):
            logger.warning("Lembrete inválido ignorado: %r", item)
            continue
        items.append(reminder)
    return items


def _save(items: List[Reminder]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([asdict(r) for r in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def add(text: str, when: datetime, idioma: Optional[str] = None) -> Reminder:
    """Guarda um lembrete. Sem ``idioma``, vale o idioma atual das ações."""
    from nicx.acoes import textos

    reminder = Reminder(
        id=uuid.uuid4().hex[:8],
        text=text.strip() or textos.texto("o_que_pediu"),
        due=when.replace(microsecond=0).isoformat(),
        created=datetime.now().replace(microsecond=0).isoformat(),
        idioma=textos.codigo(idioma),
    )
    with _LOCK:
        items = _load()
        items.append(reminder)
        _save(items)
    return reminder


def pending() -> List[Reminder]:
    with _LOCK:
        return sorted(_load(), key=lambda r: r.due)


_KIND_TEXT = {"timer": "o tempo acabou", "alarme": "alarme"}


def kind_of(reminder: Reminder) -> str:
    """'timer', 'alarme' ou 'lembrete'."""
    for kind, text in _KIND_TEXT.items():
        if reminder.text == text:
            return kind
    return "lembrete"


def cancel_all(kind: str = "") -> int:
    """Cancela todos os lembretes, ou só os de um tipo ('timer', 'alarme')."""
    with _LOCK:
        items = _load()
        keep = [r for r in items if kind and kind_of(r) != kind]
        _save(keep)
    return len(items) - len(keep)


def cancel_next(kind: str = "") -> Optional[Reminder]:
    """Cancela só o próximo lembrete (de um tipo, se dado)."""
    with _LOCK:
        items = sorted(_load(), key=lambda r: r.due)
        target = next((r for r in items if not kind or kind_of(r) == kind), None)
        if target is not None:
            _save([r for r in items if r.id != target.id])
    return target


def cancel_id(reminder_id: str) -> bool:
    """Cancela um lembrete pelo id (o aviso de um compromisso desmarcado)."""
    with _LOCK:
        items = _load()
        keep = [r for r in items if r.id != reminder_id]
        if len(keep) != len(items):
            _save(keep)
    return len(keep) != len(items)


def pop_due(now: Optional[datetime] = None) -> List[Reminder]:
    """Tira da lista e devolve os lembretes vencidos."""
    now = now or datetime.now()
    with _LOCK:
        items = _load()
        due = [r for r in items if r.due_at <= now]
        if due:
            _save([r for r in items if r.due_at > now])
            _record_fired(due, now)
    return due


# ---------------------------------------------------------------------------
# Histórico dos que já dispararam (para o resumo do dia)
# ---------------------------------------------------------------------------

# Quantos dias de histórico ficam guardados.
_HISTORY_DAYS = 14


def _history_path() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "lembretes_disparados.json"


def _load_history() -> List[dict]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return (
        [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, list)
        else []
    )


def _record_fired(due: List[Reminder], now: datetime) -> None:
    """Guarda os que dispararam agora. Melhor esforço: nunca para o aviso."""
    try:
        cutoff = (now - timedelta(days=_HISTORY_DAYS)).isoformat()
        kept = [h for h in _load_history() if str(h.get("fired", "")) >= cutoff]
        fired = now.replace(microsecond=0).isoformat()
        kept += [{**asdict(r), "fired": fired} for r in due]
        path = _history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001
        logger.info("Histórico de lembretes não gravado: %s", exc)


def fired_on(day) -> List[Reminder]:
    """Lembretes que dispararam no dia ``day`` (``datetime.date``), na ordem."""
    found: List[tuple[str, Reminder]] = []
    for item in _load_history():
        fired = str(item.get("fired", ""))
        try:
            if datetime.fromisoformat(fired).date() != day:
                continue
            fields = {k: v for k, v in item.items() if k != "fired"}
            reminder = Reminder(**fields)
            reminder.due_at
        except (TypeError, ValueError):
            continue
        found.append((fired, reminder))
    return [r for _fired, r in sorted(found, key=lambda pair: pair[0])]


def message_for(reminder: Reminder, now: Optional[datetime] = None) -> str:
    """O aviso, no idioma em que o lembrete foi pedido."""
    from nicx.acoes import textos

    now = now or datetime.now()
    idioma = reminder.idioma or textos.PADRAO
    kind = kind_of(reminder)
    if kind == "lembrete":
        text = textos.texto("aviso_lembrete", idioma, o_que=reminder.text)
    else:
        text = textos.texto(f"aviso_{kind}", idioma)
    if now - reminder.due_at > _LATE:
        text += textos.texto("aviso_atrasado", idioma, hora=f"{reminder.due_at:%H:%M}")
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


# Uma voz só para os avisos: cada get_tts_backend cria um modelo novo, e
# vários lembretes vencidos juntos carregariam vários Kokoros na RAM.
_VOICE: object = None
_VOICE_LOCK = threading.Lock()


def _voice(preferred: str):
    global _VOICE
    with _VOICE_LOCK:
        if _VOICE is None:
            from nicx.voz._tts_discovery import get_tts_backend

            _VOICE = get_tts_backend(preferred)
        return _VOICE


def speak(message: str, voice_id: str = "") -> None:
    """Fala o aviso com a voz local, se instalada. Silencioso se não houver.

    ``voice_id`` troca a voz configurada (ex.: a do idioma do texto).
    """
    try:
        import io

        import sounddevice as sd
        import soundfile as sf

        from nicx.nucleo.config import load_config

        speech = load_config().speech
        backend = _voice(getattr(speech, "tts_backend", "kokoro"))
        if backend is None:
            return
        result = backend.synthesize(
            message,
            voice_id=voice_id or getattr(speech, "voice_id", "") or "pf_dora",
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


# Outras tarefas que o despertador confere a cada volta (ex.: o resumo do dia).
_TASKS: List[Callable[[], None]] = []


def add_task(task: Callable[[], None]) -> None:
    """Pede ao despertador para chamar ``task`` a cada volta (uma vez só)."""
    if task not in _TASKS:
        _TASKS.append(task)


def remove_task(task: Callable[[], None]) -> None:
    if task in _TASKS:
        _TASKS.remove(task)


def _loop(interval: float, on_due: Callable[[Reminder], None]) -> None:
    while not _STOP.wait(interval):
        try:
            for reminder in pop_due():
                on_due(reminder)
        except Exception:  # noqa: BLE001 - o despertador nunca pode morrer
            logger.exception("Falha no despertador de lembretes")
        for task in list(_TASKS):
            try:
                task()
            except Exception:  # noqa: BLE001
                logger.exception("Falha numa tarefa do despertador")


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
