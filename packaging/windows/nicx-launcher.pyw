"""Lançador do Nicx no Windows (atalhos do menu Iniciar e da Área de Trabalho).

Garante que o Ollama esteja em execução, inicia o servidor local do Nicx em
segundo plano (sem janela de console) e abre a interface no navegador padrão.
Enquanto o servidor sobe, mostra uma pequena janela "Iniciando o Nicx...".

Uso (com o Python do ambiente do Nicx):
    pythonw.exe nicx-launcher.pyw              abre o Nicx
    pythonw.exe nicx-launcher.pyw --stop       encerra o servidor do Nicx
    python.exe  nicx-launcher.pyw --no-browser --port 8765    (testes)

Com NICX_LAUNCHER_HEADLESS=1 nada aparece na tela (sem navegador, sem janela
de abertura e sem caixas de mensagem), para testes automatizados.

Não envia dados para lugar nenhum: só conversa com 127.0.0.1.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
NICX_EXE = APP_DIR / "venv" / "Scripts" / "nicx.exe"
ICON = APP_DIR / "nicx.ico"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
START_TIMEOUT = 300.0
OLLAMA_TIMEOUT = 60.0
DEFAULT_PORT = 8000

BG = "#121211"
SURFACE = "#1a1a19"
FG = "#fcfcfb"
MUTED = "#a8a7a2"
ACCENT = "#86b6ef"
AMBER = "#eda100"

# Requests to 127.0.0.1 must never go through a system proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LaunchError(Exception):
    """A failure the user should see, with an optional log to open."""

    def __init__(self, message: str, log: Path | None = None) -> None:
        super().__init__(message)
        self.log = log


# ---------------------------------------------------------------------------
# Paths, config and state
# ---------------------------------------------------------------------------


def nicx_home() -> Path:
    """Same precedence as nicx.nucleo.paths: NICX_HOME > XDG_DATA_HOME/nicx > ~/.nicx."""
    env_home = os.environ.get("NICX_HOME")
    if env_home:
        return Path(os.path.expandvars(env_home)).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "nicx").resolve()
    return (Path.home() / ".nicx").resolve()


def load_config() -> dict:
    try:
        import tomllib

        with open(nicx_home() / "config.toml", "rb") as fh:
            return tomllib.load(fh)
    except (OSError, ValueError):
        return {}


def configured_port(config: dict) -> int:
    try:
        port = int(config.get("server", {}).get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


def uses_ollama(config: dict) -> bool:
    engine = str(config.get("engine", {}).get("default", "ollama") or "ollama")
    return engine == "ollama"


def read_server_state() -> tuple[int | None, int | None]:
    """Return (pid, port) of the registered Nicx server, if its process is alive."""
    import json

    import psutil

    home = nicx_home()
    try:
        pid = int((home / "server.pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None, None
    if pid <= 0 or not psutil.pid_exists(pid):
        return None, None
    port = None
    try:
        state = json.loads((home / "server.json").read_text(encoding="utf-8"))
        if isinstance(state, dict) and isinstance(state.get("port"), int):
            port = state["port"]
    except (OSError, ValueError):
        pass
    return pid, port


def http_status(url: str, timeout: float = 2.0) -> int | None:
    """HTTP status of *url*, or None when nothing answers."""
    try:
        with _OPENER.open(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, ValueError):
        return None


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def server_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def child_env() -> dict:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    for var in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(var, None)
    return env


def server_log() -> Path:
    return nicx_home() / "server.log"


def log_tail(path: Path, lines: int = 12) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(text[-lines:])


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


def ollama_base() -> str:
    raw = os.environ.get("OLLAMA_HOST", "").strip()
    if not raw:
        return "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = "http://" + raw
    scheme, rest = raw.split("://", 1)
    hostport = rest.split("/", 1)[0]
    host, _, port = hostport.rpartition(":") if ":" in hostport else (hostport, "", "")
    if not host:
        host, port = hostport, ""
    if host in ("0.0.0.0", "::", "[::]", ""):
        host = "127.0.0.1"
    return f"{scheme}://{host}:{port or '11434'}"


def find_ollama() -> tuple[Path | None, Path | None]:
    """Return (tray app, ollama.exe) when installed."""
    dirs = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"]
    if os.environ.get("ProgramFiles"):
        dirs.append(Path(os.environ["ProgramFiles"]) / "Ollama")
    found = shutil.which("ollama")
    if found:
        dirs.insert(0, Path(found).parent)
    for d in dirs:
        exe = d / "ollama.exe"
        if exe.is_file():
            app = d / "ollama app.exe"
            return (app if app.is_file() else None), exe
    return None, None


def ensure_ollama(status) -> None:
    base = ollama_base()
    if http_status(f"{base}/api/version") == 200:
        return
    _, exe = find_ollama()
    if exe is None:
        raise LaunchError(
            "O Ollama não está instalado. Execute o instalador do Nicx de novo "
            "para instalá-lo."
        )
    # Não liga o Ollama aqui: o servidor do Nicx liga o "ollama serve"
    # escondido quando precisa e o desliga ao sair ("Parar o Nicx"). Ligado
    # pelo lançador, ele ficaria rodando depois que o Nicx fechasse.
    status("O Nicx vai ligar o Ollama...")


# ---------------------------------------------------------------------------
# Nicx server
# ---------------------------------------------------------------------------


def running_server_url() -> str | None:
    pid, port = read_server_state()
    if pid is None or port is None:
        return None
    if http_status(f"{server_url(port)}/health") is not None:
        return server_url(port)
    return None


def pick_port(preferred: int) -> int:
    if not port_in_use(preferred):
        return preferred
    # Something else owns the configured port: use the first free one after it,
    # so repeated launches keep landing on the same address.
    for port in range(preferred + 1, preferred + 51):
        if not port_in_use(port):
            return port
    raise LaunchError(f"Nenhuma porta livre perto de {preferred} para o Nicx.")


def start_server(port: int, status) -> str:
    if not NICX_EXE.is_file():
        raise LaunchError(
            "A instalação do Nicx está incompleta. Execute o instalador "
            "NicxSetup.exe de novo para repará-la."
        )
    status("Iniciando o Nicx...")
    result = subprocess.run(
        [str(NICX_EXE), "--quiet", "start", "--port", str(port)],
        creationflags=CREATE_NO_WINDOW,
        env=child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    output = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0 and "already running" not in output.lower():
        raise LaunchError(
            "Não foi possível iniciar o servidor do Nicx.\n\n" + output.strip()[-800:],
            server_log(),
        )
    url = server_url(port)
    deadline = time.monotonic() + START_TIMEOUT
    started = time.monotonic()
    slow_notice = False
    while time.monotonic() < deadline:
        if http_status(f"{url}/health") is not None:
            return url
        elapsed = time.monotonic() - started
        if elapsed > 5:
            pid, _ = read_server_state()
            if pid is None:
                tail = log_tail(server_log())
                raise LaunchError(
                    "O servidor do Nicx parou ao iniciar."
                    + (f"\n\nÚltimas linhas do registro:\n{tail}" if tail else ""),
                    server_log(),
                )
        if elapsed > 20 and not slow_notice:
            slow_notice = True
            status("Carregando os componentes (na primeira vez demora mais)...")
        time.sleep(1.0)
    raise LaunchError(
        "O Nicx demorou demais para iniciar. Veja o registro do servidor.",
        server_log(),
    )


def ollama_ready(config: dict) -> bool:
    if not uses_ollama(config):
        return True
    return http_status(f"{ollama_base()}/api/version") == 200


def launch(port_override: int | None, status) -> str:
    config = load_config()
    if uses_ollama(config):
        ensure_ollama(status)
    url = running_server_url()
    if url:
        return url
    port = pick_port(port_override or configured_port(config))
    return start_server(port, status)


def stop_server(quiet: bool) -> int:
    if not NICX_EXE.is_file():
        return 0
    pid, _ = read_server_state()
    result = subprocess.run(
        [str(NICX_EXE), "--quiet", "stop"],
        creationflags=CREATE_NO_WINDOW,
        env=child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    if not quiet:
        message_box(
            "O Nicx foi encerrado." if pid else "O Nicx não estava em execução.",
            error=False,
        )
    return 0 if result.returncode in (0, 1) else result.returncode


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def message_box(text: str, *, error: bool = True) -> None:
    flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "Nicx", flags)
    except (AttributeError, OSError):
        print(text, file=sys.stderr)


def single_instance() -> bool:
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "Local\\NicxLauncher")
        if not handle:
            return True
        globals()["_MUTEX"] = handle  # keep it alive for the process lifetime
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return True


class Splash:
    """Small "Iniciando o Nicx..." window, driven by a worker thread."""

    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.events: queue.Queue = queue.Queue()
        root = tk.Tk()
        self.root = root
        root.withdraw()
        root.title("Nicx")
        root.configure(bg=BG)
        root.resizable(False, False)
        try:
            root.iconbitmap(default=str(ICON))
        except tk.TclError:
            pass
        scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        width, height = int(380 * scale), int(250 * scale)
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 3
        root.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(root, bg=BG)
        frame.pack(expand=True, fill="both", padx=int(20 * scale), pady=int(14 * scale))
        size = 96 if scale < 1.25 else 144 if scale < 1.75 else 192
        self.image = None
        image_path = APP_DIR / f"splash-{size}.png"
        if image_path.is_file():
            try:
                self.image = tk.PhotoImage(file=str(image_path))
            except tk.TclError:
                self.image = None
        if self.image is not None:
            tk.Label(frame, image=self.image, bg=BG).pack()
        title = tk.Frame(frame, bg=BG)
        title.pack(pady=(int(4 * scale), 0))
        tk.Label(
            title, text="Nicx", bg=BG, fg=FG, font=("Segoe UI Semibold", 16)
        ).pack(side="left")
        tk.Label(title, text="●", bg=BG, fg=AMBER, font=("Segoe UI", 9)).pack(
            side="left", anchor="n", pady=(int(4 * scale), 0)
        )
        self.status = tk.Label(
            frame,
            text="Preparando...",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            wraplength=int(330 * scale),
            justify="center",
        )
        self.status.pack(pady=(int(6 * scale), int(8 * scale)))
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Nicx.Horizontal.TProgressbar",
            troughcolor=SURFACE,
            background=ACCENT,
            bordercolor=SURFACE,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        self.bar = ttk.Progressbar(
            frame,
            mode="indeterminate",
            style="Nicx.Horizontal.TProgressbar",
            length=int(260 * scale),
        )
        self.bar.pack()
        self.bar.start(12)
        self.buttons = tk.Frame(frame, bg=BG)
        self.log: Path | None = None
        self.hidden = False
        self.failed = False
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(80, self._poll)

    def _close(self) -> None:
        # Closing while starting only hides the window: the browser still opens
        # when the server is ready. After an error it really closes.
        if self.failed:
            self.root.destroy()
        else:
            self.hidden = True
            self.root.withdraw()

    def _dark_title_bar(self) -> None:
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
            )
        except (AttributeError, OSError):
            pass

    def post(self, *event) -> None:
        self.events.put(event)

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "status":
                    self.status.configure(text=event[1])
                elif kind == "done":
                    self.status.configure(text="Abrindo o Nicx no navegador...")
                    self.root.after(900, self.root.destroy)
                    return
                elif kind == "error":
                    self.failed = True
                    if self.hidden:
                        message_box(event[1])
                        self.root.destroy()
                    else:
                        self._show_error(event[1], event[2])
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _show_error(self, message: str, log: Path | None) -> None:
        tk = self.tk
        self.bar.stop()
        self.bar.pack_forget()
        self.status.configure(text=message.split("\n\n", 1)[0], fg=FG)
        self.log = log
        self.buttons.pack(pady=(4, 0))
        if log is not None and log.is_file():
            tk.Button(
                self.buttons,
                text="Ver registro",
                command=lambda: os.startfile(str(log)),  # noqa: S606
                bg=SURFACE,
                fg=FG,
                activebackground=ACCENT,
                relief="flat",
                padx=12,
            ).pack(side="left", padx=4)
        tk.Button(
            self.buttons,
            text="Fechar",
            command=self.root.destroy,
            bg=SURFACE,
            fg=FG,
            activebackground=ACCENT,
            relief="flat",
            padx=12,
        ).pack(side="left", padx=4)
        height = self.root.winfo_height()
        self.root.geometry(f"{self.root.winfo_width()}x{max(height, 270)}")

    def run(self) -> None:
        self.root.deiconify()
        self._dark_title_bar()
        self.root.mainloop()


def run_with_splash(port: int | None, open_browser: bool) -> int:
    try:
        splash = Splash()
    except Exception:  # noqa: BLE001 - no Tk: fall back to message boxes
        splash = None

    outcome: dict = {}

    def status(text: str) -> None:
        if splash is not None:
            splash.post("status", text)

    def worker() -> None:
        try:
            url = launch(port, status)
            outcome["url"] = url
            if open_browser:
                webbrowser.open(url)
            if splash:
                splash.post("done", url)
        except LaunchError as exc:
            outcome["error"] = exc
            if splash:
                splash.post("error", str(exc), exc.log)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = LaunchError(f"Erro inesperado: {exc}", server_log())
            if splash:
                splash.post("error", str(outcome["error"]), server_log())

    if splash is None:
        worker()
    else:
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        splash.run()
        thread.join(timeout=0.1)

    if "error" in outcome:
        if splash is None:
            message_box(str(outcome["error"]))
        print(f"erro: {outcome['error']}", file=sys.stderr)
        return 1
    if "url" in outcome:
        print(outcome["url"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Abre ou encerra o Nicx.")
    parser.add_argument("--stop", action="store_true", help="encerra o servidor")
    parser.add_argument("--quiet", action="store_true", help="sem mensagens")
    parser.add_argument("--port", type=int, default=None, help="porta do servidor")
    parser.add_argument(
        "--no-browser", action="store_true", help="não abre o navegador (testes)"
    )
    parser.add_argument(
        "--no-splash", action="store_true", help="sem a janela de abertura (testes)"
    )
    args = parser.parse_args(argv)
    # Automated tests: no browser, no splash and no message boxes, so nothing
    # appears on the desktop of whoever is using the machine.
    if os.environ.get("NICX_LAUNCHER_HEADLESS") == "1":
        args.no_browser = args.no_splash = args.quiet = True

    if args.stop:
        return stop_server(args.quiet)

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

    # A server that is already up opens immediately, without the splash.
    url = running_server_url()
    if url and ollama_ready(load_config()):
        if not args.no_browser:
            webbrowser.open(url)
        print(url)
        return 0

    if not single_instance():
        return 0  # another launcher is already starting the server

    if args.no_splash:
        try:
            url = launch(args.port, lambda text: print(text, file=sys.stderr))
        except LaunchError as exc:
            if not args.quiet:
                message_box(str(exc))
            print(f"erro: {exc}", file=sys.stderr)
            return 1
        if not args.no_browser:
            webbrowser.open(url)
        print(url)
        return 0
    return run_with_splash(args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
