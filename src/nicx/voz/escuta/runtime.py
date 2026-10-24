"""Peças de sistema do "Nicx, ligar": servidor, janela do mascote, processo
da escuta e início automático com o Windows.

Tudo fala só com 127.0.0.1. Usado pelo comando ``nicx escuta``, pelo
``nicx mascote`` e pelas rotas ``/v1/speech/wake`` do servidor.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Optional

from nicx.nucleo.paths import get_config_dir

logger = logging.getLogger(__name__)

# Sem importar nicx.nucleo.config (pesado): a janela do mascote abre mais rápido.
DEFAULT_CONFIG_DIR = get_config_dir()
STATE_FILE = DEFAULT_CONFIG_DIR / "wake.json"
STOP_FILE = DEFAULT_CONFIG_DIR / "wake.stop"
LOG_FILE = DEFAULT_CONFIG_DIR / "wake.log"
WEBVIEW_DIR = DEFAULT_CONFIG_DIR / "webview-mascote"
SHORTCUT_NAME = "Nicx - escuta.lnk"

# Rota da interface com o mascote flutuante e o parâmetro que liga a conversa
# por voz quando a interface abre no navegador (plano B sem janela própria).
FLOATING_ROUTE = "/flutuante"
BROWSER_VOICE_QUERY = "/?voz=1"

_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200

# Pedidos a 127.0.0.1 nunca passam por um proxy do sistema.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------------------
# Servidor local
# ---------------------------------------------------------------------------


def server_base_url() -> str:
    """URL do servidor do Nicx: o registrado por ``nicx start``/``serve`` ou o
    da configuração. Sempre em 127.0.0.1."""
    port: Optional[int] = None
    try:
        from nicx.comandos.daemon_cmd import _read_state

        state = _read_state()
        pid = state.get("pid")
        if pid and _pid_alive(pid):
            port = state.get("port")
    except Exception as exc:
        logger.debug("Estado do servidor ilegível: %s", exc)
    if not port:
        try:
            from nicx.nucleo.config import load_config

            port = int(load_config().server.port)
        except Exception:
            port = 8000
    return f"http://127.0.0.1:{port}"


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("NICX_API_KEY", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def http_json(
    url: str, *, method: str = "GET", body: Any = None, timeout: float = 1.0
) -> Optional[dict]:
    """JSON de *url*, ou None se nada responder."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
            return payload if isinstance(payload, dict) else {}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def server_up(base: str, timeout: float = 1.0) -> bool:
    try:
        with _OPENER.open(f"{base}/health", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def remote_busy(base: str) -> bool:
    """O servidor diz que há conversa por voz ativa ou o Nicx está falando."""
    payload = http_json(f"{base}/v1/speech/wake/busy", timeout=0.5)
    return bool(payload and payload.get("busy"))


def _spawn_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def start_server() -> None:
    """Sobe o servidor em segundo plano (``nicx start``), sem janela."""
    logger.info("Servidor do Nicx fora do ar: iniciando")
    subprocess.Popen(
        [sys.executable, "-m", "nicx.comandos", "start"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **_spawn_kwargs(),
    )


def wait_for_server(base: str, timeout: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_up(base):
            return True
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Janela do mascote
# ---------------------------------------------------------------------------


def window_supported() -> bool:
    """A janela flutuante usa pywebview + WebView2 (Windows)."""
    return sys.platform == "win32" and importlib.util.find_spec("webview") is not None


def spawn_mascot(base: str, *, since: Optional[float] = None) -> subprocess.Popen:
    """Abre a janela do mascote em um processo próprio (fecha sozinha)."""
    cmd = [sys.executable, "-m", "nicx.voz.escuta.window", "--url", base]
    if since is not None:
        cmd += ["--desde", f"{since:.3f}"]
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env={**os.environ, "PYTHONUTF8": "1"},
            **_spawn_kwargs(),
        )


def open_in_browser(base: str) -> None:
    """Plano B: a interface no navegador, já em "Conversa por voz"."""
    webbrowser.open(f"{base}{BROWSER_VOICE_QUERY}")


# ---------------------------------------------------------------------------
# Processo da escuta
# ---------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    try:
        import psutil

        return psutil.pid_exists(int(pid))
    except Exception:
        return False


def _is_listener(pid: int) -> bool:
    """O PID é mesmo uma escuta do Nicx (e não um PID reaproveitado)?"""
    try:
        import psutil

        cmdline = " ".join(psutil.Process(int(pid)).cmdline())
    except Exception:
        return False
    return "nicx" in cmdline and ("escuta" in cmdline or " wake" in cmdline)


def write_state(state: str, **extra: Any) -> None:
    payload = {"pid": os.getpid(), "state": state, "updated_at": time.time(), **extra}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def clear_state() -> None:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if state.get("pid") == os.getpid():
            STATE_FILE.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def read_state() -> Optional[dict]:
    """Estado da escuta em execução, ou None se nenhuma estiver rodando."""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or type(state.get("pid")) is not int:
        return None
    if not _pid_alive(state["pid"]) or not _is_listener(state["pid"]):
        return None
    return state


def start_listener_process(*, only_if_enabled: bool = True) -> Optional[int]:
    """Inicia ``nicx escuta`` em segundo plano, se ainda não estiver rodando."""
    running = read_state()
    if running:
        return running["pid"]
    STOP_FILE.unlink(missing_ok=True)
    cmd = [sys.executable, "-m", "nicx.comandos", "escuta"]
    if only_if_enabled:
        cmd.append("--se-ativado")
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env={**os.environ, "PYTHONUTF8": "1"},
            **_spawn_kwargs(),
        )
    return proc.pid


def stop_listener(timeout: float = 4.0) -> bool:
    """Pede para a escuta sair (ela tira o ícone da bandeja); força se demorar."""
    state = read_state()
    if not state:
        return False
    STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text("parar", encoding="utf-8")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(state["pid"]):
            break
        time.sleep(0.2)
    else:
        from nicx.nucleo.utils import terminate_process

        terminate_process(state["pid"], grace_seconds=2.0)
    STOP_FILE.unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)
    return True


def stop_requested() -> bool:
    return STOP_FILE.exists()


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


def config_path() -> Path:
    return Path(os.environ.get("NICX_CONFIG", DEFAULT_CONFIG_DIR / "config.toml"))


def set_wake_enabled(enabled: bool) -> None:
    """Grava ``[speech] wake_word`` no config.toml, preservando o resto."""
    import tomlkit

    path = config_path()
    if path.exists():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = tomlkit.document()
    if "speech" not in doc:
        doc.add("speech", tomlkit.table())
    doc["speech"]["wake_word"] = bool(enabled)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# Início automático com o Windows (pasta Inicializar do usuário, sem admin)
# ---------------------------------------------------------------------------


def startup_dir() -> Optional[Path]:
    if sys.platform != "win32":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return (
        Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    )


def shortcut_path() -> Optional[Path]:
    folder = startup_dir()
    return folder / SHORTCUT_NAME if folder else None


def autostart_enabled() -> bool:
    path = shortcut_path()
    return bool(path and path.exists())


def background_python() -> str:
    """pythonw.exe ao lado do Python atual (sem janela de console no login)."""
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def set_autostart(enabled: bool) -> bool:
    """Cria ou remove o atalho na pasta Inicializar. False se não suportado."""
    path = shortcut_path()
    if path is None:
        return False
    if not enabled:
        path.unlink(missing_ok=True)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    target = background_python()

    def ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"{ps_quote(str(path))});"
        f"$s.TargetPath = {ps_quote(target)};"
        "$s.Arguments = '-m nicx.comandos escuta --se-ativado';"
        f"$s.WorkingDirectory = {ps_quote(str(DEFAULT_CONFIG_DIR))};"
        "$s.Description = 'Nicx: escuta a frase \"Nicx, ligar\" (local)';"
        "$s.WindowStyle = 7;"
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
        creationflags=_CREATE_NO_WINDOW,
        timeout=30,
    )
    return path.exists()


__all__ = [
    "BROWSER_VOICE_QUERY",
    "FLOATING_ROUTE",
    "LOG_FILE",
    "STATE_FILE",
    "WEBVIEW_DIR",
    "autostart_enabled",
    "clear_state",
    "http_json",
    "open_in_browser",
    "read_state",
    "remote_busy",
    "server_base_url",
    "server_up",
    "set_autostart",
    "set_wake_enabled",
    "spawn_mascot",
    "start_listener_process",
    "start_server",
    "stop_listener",
    "stop_requested",
    "wait_for_server",
    "window_supported",
    "write_state",
]
