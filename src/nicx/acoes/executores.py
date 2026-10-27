"""Execução das rotinas: lembretes, anotações, estado do PC, pastas, print,
fechar apps e energia. Cada função devolve uma frase curta, boa para falar.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from nicx.acoes import confirmacao, lembretes, notas
from nicx.acoes.intencoes import Action
from nicx.acoes.rotinas import CLOSABLE, FOLDERS
from nicx.acoes.sistema import Outcome, _start, _windows_only
from nicx.acoes.tempo import say_when

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ---------------------------------------------------------------------------
# Lembretes e anotações
# ---------------------------------------------------------------------------


def remind(action: Action) -> Outcome:
    when = action.when or datetime.now()
    reminder = lembretes.add(action.target, when)
    spoken = say_when(reminder.due_at)
    if action.target == "o tempo acabou":
        return Outcome(True, f"Timer marcado: aviso {spoken}.")
    if action.target == "alarme":
        return Outcome(True, f"Alarme marcado {spoken}.")
    return Outcome(True, f"Combinado: {spoken} eu te lembro de {action.target}.")


def remind_list() -> Outcome:
    items = lembretes.pending()
    if not items:
        return Outcome(True, "Você não tem lembretes marcados.")
    names = {"o tempo acabou": "timer"}
    parts = [f"{names.get(r.text, r.text)} {say_when(r.due_at)}" for r in items[:5]]
    more = f" e mais {len(items) - 5}" if len(items) > 5 else ""
    head = _plural(len(items), "lembrete", "lembretes")
    return Outcome(True, f"Você tem {head}: " + "; ".join(parts) + more + ".")


def remind_clear() -> Outcome:
    n = lembretes.cancel_all()
    if n == 0:
        return Outcome(True, "Não havia lembretes para cancelar.")
    return Outcome(True, f"Cancelei {_plural(n, 'lembrete', 'lembretes')}.")


def note_add(action: Action) -> Outcome:
    notas.add(action.target)
    return Outcome(True, "Anotado.")


def notes_list() -> Outcome:
    items = notas.all_notes()
    if not items:
        return Outcome(True, "Você ainda não tem anotações.")
    last = items[-5:]
    head = "Sua anotação" if len(items) == 1 else f"Suas últimas {len(last)} anotações"
    return Outcome(True, f"{head}: " + "; ".join(last) + ".")


def notes_clear() -> Outcome:
    n = notas.clear()
    return Outcome(True, f"Apaguei {_plural(n, 'anotação', 'anotações')}.")


# ---------------------------------------------------------------------------
# Estado do PC
# ---------------------------------------------------------------------------


def _gb(n: float) -> str:
    return f"{n / 1024**3:.1f}".replace(".", ",")


def status() -> Outcome:
    import psutil

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    parts = [
        f"processador em {cpu:.0f}%",
        f"memória {mem.percent:.0f}% usada ({_gb(mem.available)} GB livres)",
    ]
    try:
        disk = psutil.disk_usage(Path.home().anchor or "/")
        parts.append(f"disco com {_gb(disk.free)} GB livres")
    except OSError:
        pass
    try:
        battery = psutil.sensors_battery()
    except Exception:  # noqa: BLE001 - sem sensor, sem bateria na frase
        battery = None
    if battery is not None:
        charging = ", carregando" if battery.power_plugged else ""
        parts.append(f"bateria em {round(battery.percent)}%{charging}")

    # Quem mais pesa na memória, somando as várias janelas de cada programa.
    usage: dict[str, int] = {}
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (proc.info["name"] or "").removesuffix(".exe")
            usage[name] = usage.get(name, 0) + proc.info["memory_info"].rss
        except (psutil.Error, AttributeError, TypeError):
            continue
    heavy = sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:2]
    message = "Agora: " + ", ".join(parts) + "."
    if heavy and mem.percent >= 70:
        top = " e ".join(f"{n} ({_gb(b)} GB)" for n, b in heavy)
        message += f" O que mais usa memória: {top}."
    return Outcome(True, message)


# ---------------------------------------------------------------------------
# Pastas e print
# ---------------------------------------------------------------------------


def folder_path(key: str) -> Optional[Path]:
    home = Path.home()
    for candidate in FOLDERS[key][1]:
        path = home / candidate
        if path.is_dir():
            return path
    return None


def folder(action: Action) -> Outcome:
    label = FOLDERS[action.target][0]
    path = folder_path(action.target)
    if path is None:
        return Outcome(False, f"Não achei a pasta {label}.")
    _start(str(path))
    return Outcome(True, f"Abrindo {label}.")


def screenshot() -> Outcome:
    try:
        from PIL import ImageGrab
    except ImportError:
        return Outcome(False, "Para tirar print eu preciso do pacote Pillow.")
    base = folder_path("imagens") or Path.home()
    target_dir = base / "Nicx"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"print-{datetime.now():%Y%m%d-%H%M%S}.png"
    ImageGrab.grab(all_screens=True).save(target)
    return Outcome(True, f"Print salvo em {base.name}\\Nicx.")


# ---------------------------------------------------------------------------
# Fechar apps
# ---------------------------------------------------------------------------


def close(action: Action) -> Outcome:
    import psutil

    label, exes = CLOSABLE[action.target]
    wanted = {e.lower() for e in exes}
    running = {
        (p.info["name"] or "")
        for p in psutil.process_iter(["name"])
        if (p.info["name"] or "").lower() in wanted
    }
    if not running:
        return Outcome(True, f"{label[0].upper()}{label[1:]} não está aberto.")
    if sys.platform == "win32":
        # Sem /F: o programa recebe o pedido de fechar e pode perguntar se
        # quer salvar, como ao clicar no X.
        for exe in running:
            subprocess.run(  # noqa: S603, S607
                ["taskkill", "/IM", exe], capture_output=True, creationflags=_NO_WINDOW
            )
    else:
        for proc in psutil.process_iter(["name"]):
            if (proc.info["name"] or "") in running:
                proc.terminate()
    return Outcome(True, f"Fechando {label}.")


# ---------------------------------------------------------------------------
# Energia (sempre com confirmação)
# ---------------------------------------------------------------------------

_POWER_ASK = {
    "shutdown": "desligar o computador",
    "restart": "reiniciar o computador",
    "suspend": "suspender o computador",
}


def power(action: Action) -> Outcome:
    if action.op == "abort":
        if sys.platform != "win32":
            return _windows_only()
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/a"], capture_output=True, creationflags=_NO_WINDOW
        )
        return Outcome(True, "Desligamento cancelado.")
    confirmacao.ask(action)
    return Outcome(
        True,
        f"Tem certeza que quer {_POWER_ASK[action.op]}? "
        'Diga "confirmo" em até 30 segundos.',
    )


def confirm() -> Outcome:
    action = confirmacao.take()
    if action is None:
        return Outcome(False, "Não há nada esperando confirmação.")
    if sys.platform != "win32":
        return _windows_only()
    if action.op == "shutdown":
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/s", "/t", "30"],
            capture_output=True,
            creationflags=_NO_WINDOW,
        )
        return Outcome(
            True,
            'Desligando em 30 segundos. Para cancelar, diga "cancela o desligamento".',
        )
    if action.op == "restart":
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/r", "/t", "30"],
            capture_output=True,
            creationflags=_NO_WINDOW,
        )
        return Outcome(
            True,
            'Reiniciando em 30 segundos. Para cancelar, diga "cancela o reinício".',
        )
    # Suspender corta tudo na hora: espera a resposta chegar antes.
    threading.Timer(
        3.0,
        lambda: subprocess.run(  # noqa: S603, S607
            ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            capture_output=True,
            creationflags=_NO_WINDOW,
        ),
    ).start()
    return Outcome(True, "Suspendendo em 3 segundos.")


def deny() -> Outcome:
    confirmacao.drop()
    return Outcome(True, "Tudo bem, não vou fazer nada.")


def run(action: Action) -> Optional[Outcome]:
    """Executa uma rotina; None se a ação não for uma rotina."""
    simple = {
        "remind_list": remind_list,
        "remind_clear": remind_clear,
        "notes_list": notes_list,
        "notes_clear": notes_clear,
        "status": status,
        "screenshot": screenshot,
        "confirm": confirm,
        "deny": deny,
    }
    if action.kind in simple:
        return simple[action.kind]()
    with_action = {
        "remind": remind,
        "note_add": note_add,
        "folder": folder,
        "close": close,
        "power": power,
    }
    if action.kind in with_action:
        return with_action[action.kind](action)
    return None
