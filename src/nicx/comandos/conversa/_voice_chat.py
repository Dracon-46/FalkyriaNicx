"""Voice input/output helpers for the interactive chat session."""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from rich.markup import escape

VOICE_EXIT = object()

logger = logging.getLogger(__name__)

# Backend selection is shared with the API server and lives in
# nicx.voz._tts_discovery. Importing that at module level would pull
# the whole speech stack -- numpy included -- into every `nicx` invocation,
# which tests/comandos/test_cli.py guards against, so these aliases resolve lazily.
_LAZY_TTS_NAMES = {
    "_TTS_BACKEND_ORDER": "TTS_BACKEND_ORDER",
    "_BACKEND_DEFAULT_VOICE": "BACKEND_DEFAULT_VOICE",
}


def __getattr__(name: str) -> Any:
    target = _LAZY_TTS_NAMES.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from nicx.voz import _tts_discovery

    return getattr(_tts_discovery, target)


def _terminal_safe_text(value: object) -> str:
    """Remove terminal controls and escape Rich markup from dynamic text."""
    printable = "".join(
        char for char in str(value) if char in ("\n", "\t") or char.isprintable()
    )
    return escape(printable)


class VoiceSession:
    """Cache healthy speech backends for one interactive chat session."""

    def __init__(self, config: object | None = None) -> None:
        self._config = config
        self._stt_resolved = False
        self._stt_backend: Any = None
        self._tts_backend: Any = None
        self._tts_attempted: set[str] = set()
        self._voice_prefs: tuple[str, str, float] | None = None
        self._voice_warned: set[str] = set()
        # Guards backend resolution: prewarm() loads models on a background
        # thread, and the chat loop must wait for that load, not start another.
        self._lock = threading.RLock()

    def prewarm(self) -> None:
        """Load the speech models in the background.

        Kokoro takes 10-20 s to load on a CPU; doing it while the user speaks
        and the model thinks keeps that wait out of the first spoken reply.
        """

        def _load() -> None:
            try:
                self.get_stt_backend()
                self.get_tts_backend()
            except Exception:  # noqa: BLE001 - surfaced again on first real use
                logger.debug("Voice prewarm failed", exc_info=True)

        threading.Thread(target=_load, name="nicx-voice-prewarm", daemon=True).start()

    def get_stt_backend(self) -> Any:
        """Resolve and health-check STT once, then reuse the loaded backend."""
        with self._lock:
            if not self._stt_resolved:
                from nicx.nucleo.config import load_config
                from nicx.voz._discovery import get_speech_backend

                config = self._config if self._config is not None else load_config()
                self._stt_backend = get_speech_backend(config)
                self._stt_resolved = True
            return self._stt_backend

    def get_stt_language(self) -> Optional[str]:
        """Return the configured ``speech.language``, or None to auto-detect."""
        from nicx.nucleo.config import load_config

        config = self._config if self._config is not None else load_config()
        return (getattr(config.speech, "language", "") or "").strip() or None

    def get_tts_backend(self) -> Any:
        """Return a cached healthy TTS backend, falling through once per key."""
        with self._lock:
            if self._tts_backend is not None:
                return self._tts_backend

            from nicx.voz._tts_discovery import get_tts_backend

            preferred, _, _ = self.get_voice_preferences()
            self._tts_backend = get_tts_backend(
                preferred, attempted=self._tts_attempted
            )
            return self._tts_backend

    def get_voice_preferences(self) -> tuple[str, str, float]:
        """Resolve configured (tts_backend, voice_id, speed), cached per session."""
        if self._voice_prefs is None:
            from nicx.nucleo.config import load_config
            from nicx.voz._tts_discovery import voice_preferences

            config = self._config if self._config is not None else load_config()
            self._voice_prefs = voice_preferences(config)
        return self._voice_prefs

    def voice_for_backend(self, backend: Any, console: Any = None) -> tuple[str, float]:
        """Return the voice ID valid for ``backend``, plus the configured speed.

        Voice IDs are not portable across backends, so the configured
        ``speech.voice_id`` is honored only when ``backend`` is the configured
        ``speech.tts_backend``. Otherwise the fallback backend's own default is
        used and the substitution is reported once per session.
        """
        want_backend, voice_id, speed = self.get_voice_preferences()
        active = getattr(backend, "backend_id", "") or ""
        if active == want_backend:
            return voice_id, speed

        from nicx.voz._tts_discovery import default_voice_for

        substitute = default_voice_for(active)
        if console is not None and active not in self._voice_warned:
            self._voice_warned.add(active)
            console.print(
                f"[dim yellow]Voz: {want_backend!r} indisponível — usando "
                f"{active!r} com a voz padrão "
                f"({substitute or 'a do próprio mecanismo'}).[/dim yellow]"
            )
        return substitute, speed

    def discard_tts_backend(self) -> None:
        """Forget a backend that failed synthesis and allow the next fallback."""
        self._tts_backend = None


def read_voice_input(console: Any, session: VoiceSession) -> Optional[str] | object:
    """Accept a typed command/message, or record after an empty submission."""
    try:
        typed = input("Você> [digite, ou tecle Enter para falar] ")
    except (EOFError, KeyboardInterrupt):
        return VOICE_EXIT
    typed = typed.strip()
    return typed if typed else record_voice(console, session)


def record_voice(
    console: Any,
    session: VoiceSession | None = None,
) -> Optional[str] | object:
    """Record from mic, transcribe, and return text or a loop sentinel."""
    from nicx.voz.voice_io import record_until_silence

    active_session = session or VoiceSession()
    backend = active_session.get_stt_backend()
    if backend is None:
        console.print(
            "[red]Nenhum reconhecimento de voz disponível. Instale as "
            "dependências de voz (local, sem custo): uv sync --extra speech "
            "--extra voice, junto com os extras que você já usa.[/red]"
        )
        return VOICE_EXIT

    console.print(
        "[dim cyan]Ouvindo… (fale agora; a gravação para quando você "
        "fica em silêncio)[/dim cyan]"
    )
    try:
        audio_bytes = record_until_silence()
    except KeyboardInterrupt:
        return VOICE_EXIT
    except Exception as exc:
        # PortAudio failures are regular Exceptions (and can surface as
        # OSError), so report them without letting terminal control sequences
        # through. SystemExit deliberately continues to propagate, while
        # Ctrl-C maps to the chat loop's graceful-exit sentinel above.
        console.print(f"[red]Erro no microfone: {_terminal_safe_text(exc)}[/red]")
        return VOICE_EXIT

    console.print("[dim]Transcrevendo…[/dim]")
    try:
        result = backend.transcribe(
            audio_bytes, format="wav", language=active_session.get_stt_language()
        )
        text = result.text.strip()
        if text:
            console.print(f"[bold]Você (voz):[/bold] {_terminal_safe_text(text)}")
            return text
        console.print("[dim]Não ouvi nada — tente de novo.[/dim]")
        return None
    except Exception as exc:
        console.print(f"[red]Erro na transcrição: {_terminal_safe_text(exc)}[/red]")
        return None


def start_continuous_speech(console: Any, session: VoiceSession) -> Any:
    """Fala frase a frase enquanto a resposta chega; None sem voz disponível.

    Use ``.adicionar(pedaco)`` a cada pedaço do stream e ``.terminar()`` no
    fim (ou ``.cancelar()``). Erro de síntese fica em ``.erro``.
    """
    from nicx.comandos.conversa._fala_continua import FalaContinua
    from nicx.voz.voice_io import play_wav

    try:
        session.get_voice_preferences()
        backend = session.get_tts_backend()
        if backend is None:
            return None
        voice_id, speed = session.voice_for_backend(backend, console)
    except Exception as exc:
        console.print(
            f"[red]Configuração de voz inválida: {_terminal_safe_text(exc)}[/red]"
        )
        return None

    def sintetizar(frase: str) -> tuple[bytes, int] | None:
        kwargs: dict[str, Any] = {"output_format": "wav", "speed": speed}
        if voice_id:
            kwargs["voice_id"] = voice_id
        result = backend.synthesize(frase, **kwargs)
        return (result.audio, result.sample_rate) if result.audio else None

    return FalaContinua(
        sintetizar, lambda audio, taxa: play_wav(audio, sample_rate=taxa)
    )


def speak(text: str, console: Any, session: VoiceSession | None = None) -> None:
    """Synthesize and play text, reusing a healthy backend for the session."""
    from nicx.voz.voice_io import play_wav

    active_session = session or VoiceSession()

    # Resolved before the loop: a bad config value must surface as a config
    # error, not be swallowed by the per-backend fallback handler below.
    try:
        active_session.get_voice_preferences()
    except Exception as exc:
        console.print(
            f"[red]Configuração de voz inválida: {_terminal_safe_text(exc)}[/red]"
        )
        return

    while (backend := active_session.get_tts_backend()) is not None:
        try:
            voice_id, speed = active_session.voice_for_backend(backend, console)
            synth_kwargs: dict[str, Any] = {"output_format": "wav", "speed": speed}
            if voice_id:
                synth_kwargs["voice_id"] = voice_id
            result = backend.synthesize(text, **synth_kwargs)
            if result.audio:
                play_wav(result.audio, sample_rate=result.sample_rate)
            return
        except Exception as exc:
            console.print(
                f"[dim yellow]A voz "
                f"{getattr(backend, 'backend_id', '?')!r} falhou: "
                f"{_terminal_safe_text(exc)}[/dim yellow]"
            )
            active_session.discard_tts_backend()

    console.print(
        "[dim yellow]Nenhuma voz disponível — instale o Kokoro: "
        "uv sync --extra voice[/dim yellow]"
    )


__all__ = [
    "VOICE_EXIT",
    "VoiceSession",
    "read_voice_input",
    "record_voice",
    "speak",
    "start_continuous_speech",
]
