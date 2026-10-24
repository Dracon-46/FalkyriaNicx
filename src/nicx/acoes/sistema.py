"""Executa as ações no computador e devolve uma frase curta para falar.

Volume e mídia usam as teclas multimídia do Windows (as mesmas do teclado),
então funcionam com qualquer player e sem bibliotecas extras. Fora do Windows,
só abrir sites, hora, data e bateria funcionam.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote_plus

from nicx.acoes.intencoes import APPS, Action

logger = logging.getLogger(__name__)

_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_VK_MEDIA_NEXT = 0xB0
_VK_MEDIA_PREV = 0xB1
_VK_MEDIA_PLAY_PAUSE = 0xB3
_KEYEVENTF_KEYUP = 0x0002
# Do zero ao máximo são 50 toques (2% cada).
_VOLUME_KEY_STEPS = 50

_WEEKDAYS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
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
_SEARCH_URLS = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
}


@dataclass(frozen=True)
class Outcome:
    ok: bool
    message: str  # frase curta, boa para ser falada


def _press(vk: int, times: int = 1) -> None:
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def _windows_only() -> Outcome:
    return Outcome(False, "Isso eu só sei fazer no Windows por enquanto.")


def _volume(action: Action) -> Outcome:
    if sys.platform != "win32":
        return _windows_only()
    if action.op == "mute":
        _press(_VK_VOLUME_MUTE)
        return Outcome(True, "Pronto, alternei o mudo.")
    if action.op == "set":
        level = max(0, min(100, action.value or 0))
        # Sem ler o nível atual: zera e sobe até o pedido.
        _press(_VK_VOLUME_DOWN, _VOLUME_KEY_STEPS)
        _press(_VK_VOLUME_UP, round(level / 2))
        return Outcome(True, f"Volume em {level}%.")
    steps = action.value or 5
    if action.op == "up":
        _press(_VK_VOLUME_UP, steps)
        return Outcome(True, "Aumentei o volume.")
    _press(_VK_VOLUME_DOWN, steps)
    return Outcome(True, "Abaixei o volume.")


def _media(action: Action) -> Outcome:
    if sys.platform != "win32":
        return _windows_only()
    key, message = {
        "toggle": (_VK_MEDIA_PLAY_PAUSE, "Pronto."),
        "next": (_VK_MEDIA_NEXT, "Próxima."),
        "prev": (_VK_MEDIA_PREV, "Voltei para a anterior."),
    }[action.op]
    _press(key)
    return Outcome(True, message)


def _start(target: str) -> None:
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        import subprocess

        subprocess.Popen(["open", target])  # noqa: S603, S607
    else:
        import subprocess

        subprocess.Popen(["xdg-open", target])  # noqa: S603, S607


def _open(action: Action) -> Outcome:
    app = APPS[action.target]
    try:
        if app.kind == "url":
            webbrowser.open(app.value)
        elif app.kind == "uri":
            _start(app.value)
        else:
            if sys.platform != "win32":
                return _windows_only()
            # Programas no PATH (code.cmd) ou registrados no Windows (chrome).
            _start(shutil.which(app.value) or app.value)
    except OSError as exc:
        logger.info("Não abriu %s: %s", app.value, exc)
        return Outcome(False, f"Não encontrei {app.label} neste computador.")
    return Outcome(True, f"Abrindo {app.label}.")


def _search(action: Action) -> Outcome:
    url = _SEARCH_URLS[action.site].format(quote_plus(action.target))
    webbrowser.open(url)
    where = "no YouTube" if action.site == "youtube" else "no Google"
    return Outcome(True, f"Pesquisando {action.target} {where}.")


def _time() -> Outcome:
    now = datetime.now()
    if now.minute == 0:
        return Outcome(True, f"São {now.hour}h em ponto.")
    return Outcome(True, f"São {now.hour}h{now.minute:02d}.")


def _date() -> Outcome:
    now = datetime.now()
    weekday = _WEEKDAYS[now.weekday()]
    return Outcome(True, f"Hoje é {weekday}, {now.day} de {_MONTHS[now.month - 1]}.")


def _battery() -> Outcome:
    try:
        import psutil

        battery = psutil.sensors_battery()
    except Exception:  # noqa: BLE001 - sem sensor é o mesmo que sem bateria
        battery = None
    if battery is None:
        return Outcome(False, "Não encontrei bateria neste computador.")
    charging = ", carregando" if battery.power_plugged else ""
    return Outcome(True, f"Bateria em {round(battery.percent)}%{charging}.")


def _lock() -> Outcome:
    if sys.platform != "win32":
        return _windows_only()
    import ctypes

    ctypes.windll.user32.LockWorkStation()  # type: ignore[attr-defined]
    return Outcome(True, "Tela bloqueada.")


def run(action: Action) -> Outcome:
    """Executa a ação. Nunca levanta: falhas viram uma frase explicando."""
    try:
        if action.kind == "volume":
            return _volume(action)
        if action.kind == "media":
            return _media(action)
        if action.kind == "open":
            return _open(action)
        if action.kind == "search":
            return _search(action)
        if action.kind == "time":
            return _time()
        if action.kind == "date":
            return _date()
        if action.kind == "battery":
            return _battery()
        if action.kind == "lock":
            return _lock()
    except Exception as exc:  # noqa: BLE001 - a resposta explica a falha
        logger.warning("Ação %s falhou: %s", action, exc)
        return Outcome(False, "Não consegui fazer isso agora.")
    return Outcome(False, "Não sei fazer isso ainda.")
