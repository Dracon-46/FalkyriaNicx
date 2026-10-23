"""``nicx escuta`` (frase de ativação "Nicx, ligar") e ``nicx mascote``."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console

logger = logging.getLogger("nicx.escuta")


def _setup_logging(verbose: bool) -> None:
    from nicx.wake import runtime as rt

    rt.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None or sys.stderr is None:
        # pythonw (início automático): sem console, tudo vai para o wake.log.
        log = open(rt.LOG_FILE, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    handlers: list[logging.Handler] = []
    # Com stdout redirecionado (processo em segundo plano), o próprio log já
    # é o wake.log; senão grava nele e também mostra no terminal.
    if not sys.stdout.isatty():
        handlers.append(logging.StreamHandler(sys.stderr))
    else:
        handlers.append(logging.FileHandler(rt.LOG_FILE, encoding="utf-8"))
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    # O ``nicx`` da CLI fica em WARNING com um console próprio: aqui o registro
    # da escuta vai pelos manipuladores acima.
    nicx_logger = logging.getLogger("nicx")
    nicx_logger.handlers.clear()
    nicx_logger.propagate = True
    nicx_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("faster_whisper", "httpx", "httpcore", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _skip_torch() -> None:
    """A escuta roda em processo próprio e não usa PyTorch, mas o ctranslate2
    (Whisper) o importa se estiver instalado: ~150 MB a mais de RAM parada.
    Sem ele, o ctranslate2 segue normalmente (a importação é opcional lá)."""
    if "torch" not in sys.modules:
        sys.modules["torch"] = None  # type: ignore[assignment]


def _speech_config() -> Any:
    from nicx.core.config import load_config

    return load_config().speech


def _missing_deps() -> list[str]:
    import importlib.util

    return [
        name
        for name in ("numpy", "sounddevice", "faster_whisper", "onnxruntime")
        if importlib.util.find_spec(name) is None
    ]


def _tray_image() -> Any:
    from PIL import Image, ImageDraw

    static = Path(__file__).resolve().parents[1] / "server" / "static"
    for name in ("pwa-192x192.png", "apple-touch-icon.png"):
        path = static / name
        if path.is_file():
            try:
                return Image.open(path).convert("RGBA").resize((64, 64))
            except Exception:
                pass
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 10, 58, 58), fill=(95, 211, 232, 255))
    draw.ellipse((22, 26, 30, 36), fill=(11, 42, 49, 255))
    draw.ellipse((36, 26, 44, 36), fill=(11, 42, 49, 255))
    draw.ellipse((46, 8, 56, 18), fill=(237, 161, 0, 255))
    return image


class _Tray:
    """Ícone na bandeja: mostra que a escuta está ligada; Pausar / Sair."""

    def __init__(self, *, on_pause, on_open, on_quit, is_paused) -> None:  # noqa: ANN001
        self._icon: Any = None
        self._on_pause = on_pause
        self._on_open = on_open
        self._on_quit = on_quit
        self._is_paused = is_paused

    def start(self) -> bool:
        try:
            import pystray
        except Exception as exc:
            logger.info("Ícone da bandeja indisponível (%s)", exc)
            return False
        item = pystray.MenuItem
        menu = pystray.Menu(
            item('Escutando "Nicx, ligar"', None, enabled=False),
            item("Abrir o Nicx agora", lambda: self._on_open()),
            item(
                "Pausar a escuta",
                lambda: self._on_pause(),
                checked=lambda _item: self._is_paused(),
            ),
            pystray.Menu.SEPARATOR,
            item("Sair", lambda: self._on_quit()),
        )
        self._icon = pystray.Icon(
            "nicx-escuta", _tray_image(), 'Nicx: escutando "Nicx, ligar"', menu
        )
        threading.Thread(target=self._icon.run, daemon=True).start()
        return True

    def set_title(self, title: str) -> None:
        if self._icon is not None:
            try:
                self._icon.title = title
            except Exception:
                pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass


class _WakeController:
    """O que acontece ao ouvir a frase, e o estado mostrado a quem pergunta."""

    def __init__(self, *, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.child: Optional[subprocess.Popen] = None
        self.listener: Any = None
        self._lock = threading.Lock()

    # -- ocupado -----------------------------------------------------------
    def window_open(self) -> bool:
        child = self.child
        if child is None:
            return False
        if child.poll() is None:
            return True
        # A janela acabou de fechar: uma folga para a última fala não reativar.
        self.child = None
        if self.listener is not None:
            self.listener.trigger.hold(3.0)
        logger.info("Janela do mascote fechada")
        return False

    def busy(self) -> bool:
        from nicx.wake import runtime as rt

        return self.window_open() or rt.remote_busy(rt.server_base_url())

    # -- ativação ------------------------------------------------------------
    def wake(self, since: Optional[float] = None) -> None:
        from nicx.wake import runtime as rt

        with self._lock:
            if self.window_open():
                return
            if self.dry_run:
                logger.info("Modo teste: a janela não é aberta")
                return
            base = rt.server_base_url()
            if not rt.server_up(base, timeout=0.5):
                rt.start_server()
            if rt.window_supported():
                self.child = rt.spawn_mascot(base, since=since)
                logger.info("Abrindo o mascote (processo %s)", self.child.pid)
            else:

                def fallback() -> None:
                    if rt.wait_for_server(base):
                        rt.open_in_browser(base)

                threading.Thread(target=fallback, daemon=True).start()
                logger.info("Sem janela própria: abrindo a interface no navegador")


@click.group(invoke_without_command=True)
@click.option(
    "--se-ativado",
    is_flag=True,
    help="Só escuta se [speech] wake_word = true (usado no início automático).",
)
@click.option("--sem-janela", is_flag=True, help="Modo teste: só registra a ativação.")
@click.option("--sem-icone", is_flag=True, help="Não mostra o ícone na bandeja.")
@click.option("--modelo", default=None, help="Modelo do Whisper (tiny, base...).")
@click.option("-v", "--verbose", is_flag=True, help="Registra cada fala detectada.")
@click.pass_context
def escuta(
    ctx: click.Context,
    se_ativado: bool,
    sem_janela: bool,
    sem_icone: bool,
    modelo: Optional[str],
    verbose: bool,
) -> None:
    """Escuta "Nicx, ligar" em segundo plano e faz o mascote aparecer.

    O microfone fica aberto só neste computador: nenhum áudio é gravado em
    disco nem enviado. Só falas curtas (até ~3 s) são transcritas, localmente.
    """
    if ctx.invoked_subcommand is not None:
        return
    from nicx.wake import runtime as rt
    from nicx.wake.detector import MicrophoneSource, build_listener

    console = Console(stderr=True)
    _setup_logging(verbose)
    cfg = _speech_config()
    if se_ativado and not cfg.wake_word:
        logger.info("Escuta desativada em [speech] wake_word; saindo")
        return
    running = rt.read_state()
    if running:
        console.print(
            f"[yellow]A escuta já está rodando (PID {running['pid']}).[/yellow]"
        )
        return
    missing = _missing_deps()
    if missing:
        raise click.ClickException(
            "Faltam pacotes de voz: " + ", ".join(missing) + ". Instale os extras "
            "'speech' e 'voice' (veja o CLAUDE.md)."
        )

    _skip_torch()
    phrases = list(cfg.wake_phrases) or None
    controller = _WakeController(dry_run=sem_janela)

    def on_wake(event: Any) -> None:
        logger.info(
            "Ativado por %r (ouvi %r; transcrição %.2f s)",
            event.phrase,
            event.text,
            event.transcribe_s,
        )
        controller.wake(since=event.speech_end)

    def on_segment(result: Any) -> None:
        if verbose:
            logger.debug(
                "Fala de %.1f s: %r -> %s%s",
                result.duration_s,
                result.text,
                result.phrase or "nada",
                f" ({result.skipped})" if result.skipped else "",
            )

    kwargs: dict = {}
    if phrases:
        kwargs["phrases"] = phrases
    listener = build_listener(
        model_size=modelo or cfg.wake_model or "base",
        language=cfg.language or "pt",
        hotwords="Nicx",
        is_busy=controller.busy,
        on_wake=on_wake,
        on_segment=on_segment,
        **kwargs,
    )
    controller.listener = listener
    # Carrega o Whisper já, para a primeira ativação não esperar por ele.
    threading.Thread(target=listener.transcribe.load, daemon=True).start()

    def toggle_pause() -> None:
        if listener.trigger.paused:
            listener.trigger.resume()
            logger.info("Escuta retomada")
        else:
            listener.trigger.pause()
            logger.info("Escuta pausada")

    tray = _Tray(
        on_pause=toggle_pause,
        on_open=lambda: controller.wake(),
        on_quit=listener.stop,
        is_paused=lambda: listener.trigger.paused,
    )
    if not sem_icone:
        tray.start()

    phrases_shown = list(listener.matcher.phrases)
    rt.write_state("escutando", phrases=phrases_shown, started_at=time.time())

    def watch() -> None:
        last = ""
        while not listener.stopped:
            if rt.stop_requested():
                logger.info("Pedido para parar recebido")
                listener.stop()
                break
            if listener.trigger.paused:
                state = "pausado"
            elif controller.window_open():
                state = "mascote aberto"
            else:
                state = "escutando"
            if state != last:
                rt.write_state(state, phrases=phrases_shown)
                tray.set_title(
                    "Nicx: escuta pausada"
                    if state == "pausado"
                    else 'Nicx: escutando "Nicx, ligar"'
                )
                last = state
            time.sleep(1.0)

    threading.Thread(target=watch, daemon=True).start()
    logger.info(
        "Escutando %s (Whisper %s, local). Ctrl+C para sair.",
        ", ".join(f'"{p}"' for p in phrases_shown),
        listener.transcribe.model_size,
    )
    try:
        listener.run(MicrophoneSource())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.error("A escuta parou: %s", exc)
        raise click.ClickException(f"Não consegui abrir o microfone: {exc}") from exc
    finally:
        listener.stop()
        tray.stop()
        rt.clear_state()
        logger.info("Escuta encerrada")


@escuta.command("parar")
def escuta_parar() -> None:
    """Encerra a escuta em segundo plano."""
    from nicx.wake import runtime as rt

    console = Console(stderr=True)
    if rt.stop_listener():
        console.print("[green]Escuta encerrada.[/green]")
    else:
        console.print("A escuta não estava rodando.")


@escuta.command("status")
def escuta_status() -> None:
    """Mostra se a escuta está ligada."""
    from nicx.wake import runtime as rt

    console = Console()
    cfg = _speech_config()
    state = rt.read_state()
    console.print(f"Ativada na configuração: {'sim' if cfg.wake_word else 'não'}")
    if state:
        console.print(f"Rodando: sim (PID {state['pid']}, {state.get('state', '?')})")
    else:
        console.print("Rodando: não")
    console.print(
        f"Iniciar com o Windows: {'sim' if rt.autostart_enabled() else 'não'}"
    )
    console.print(
        f"Janela flutuante: {'sim' if rt.window_supported() else 'não (navegador)'}"
    )
    console.print(f"Registro: {rt.LOG_FILE}")


@escuta.command("testar")
@click.argument("arquivos", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--modelo", default=None, help="Modelo do Whisper (tiny, base...).")
def escuta_testar(arquivos: tuple[str, ...], modelo: Optional[str]) -> None:
    """Passa arquivos de áudio pelo detector (nada é aberto nem disparado)."""
    from nicx.wake.detector import build_listener, iter_file_frames

    console = Console()
    cfg = _speech_config()
    _skip_torch()
    kwargs: dict = {}
    if cfg.wake_phrases:
        kwargs["phrases"] = list(cfg.wake_phrases)
    listener = build_listener(
        model_size=modelo or cfg.wake_model or "base",
        language=cfg.language or "pt",
        **kwargs,
    )
    started = time.perf_counter()
    listener.transcribe.load()
    console.print(
        f"Whisper {listener.transcribe.model_size} carregado em "
        f"{time.perf_counter() - started:.1f} s"
    )
    hits = 0
    for path in arquivos:
        listener.trigger._quiet_until = 0.0  # cada arquivo é independente
        results = listener.run_frames(iter_file_frames(path))
        fired = any(r.fired for r in results)
        hits += fired
        detail = (
            "; ".join(
                f"{r.duration_s:.1f} s -> {r.text!r} ({r.transcribe_s:.2f} s)"
                for r in results
            )
            or "nenhuma fala curta"
        )
        mark = "[green]ATIVA[/green]" if fired else "[dim]não ativa[/dim]"
        console.print(f"{mark}  {Path(path).name}: {detail}")
    console.print(f"{hits} de {len(arquivos)} arquivos ativaram.")


@escuta.command("autostart")
@click.argument("estado", type=click.Choice(["on", "off", "sim", "nao"]))
def escuta_autostart(estado: str) -> None:
    """Inicia (ou não) a escuta junto com o Windows."""
    from nicx.wake import runtime as rt

    enabled = estado in ("on", "sim")
    if not rt.set_autostart(enabled):
        raise click.ClickException("Início automático só é suportado no Windows.")
    Console().print(
        "Escuta vai iniciar com o Windows (se estiver ativada)."
        if enabled
        else "Escuta não inicia mais com o Windows."
    )


@click.command("mascote")
@click.option("--url", default=None, help="Endereço do servidor do Nicx.")
@click.option("--desde", type=float, default=None, hidden=True)
def mascote(url: Optional[str], desde: Optional[float]) -> None:
    """Abre o mascote flutuante, já ouvindo (conversa por voz)."""
    from nicx.wake import runtime as rt
    from nicx.wake.window import run_mascot_window

    _setup_logging(False)
    base = (url or rt.server_base_url()).rstrip("/")
    if not rt.server_up(base, timeout=0.5) and url is None:
        rt.start_server()
    sys.exit(run_mascot_window(base, since=desde))


__all__ = ["escuta", "mascote"]
