"""Faster-Whisper speech-to-text backend (local, CTranslate2-based)."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import List, Optional

from nicx.nucleo.registry import SpeechRegistry
from nicx.voz._ocioso import IdleRelease
from nicx.voz._stubs import Segment, SpeechBackend, TranscriptionResult

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment, misc]

try:
    import ctranslate2
except ImportError:
    ctranslate2 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def _likely_not_speech(segment: object) -> bool:
    """Whisper's own rule for text made up from noise or silence."""
    no_speech = getattr(segment, "no_speech_prob", None)
    logprob = getattr(segment, "avg_logprob", None)
    if not isinstance(no_speech, (int, float)) or not isinstance(logprob, (int, float)):
        return False
    return no_speech > 0.6 and logprob < -1.0


def _collapse_repeats(text: str, limit: int = 3) -> str:
    """Keep one copy of a sentence repeated ``limit`` or more times in a row."""
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    out: list[str] = []
    i = 0
    while i < len(sentences):
        j = i
        while (
            j + 1 < len(sentences) and sentences[j + 1].lower() == sentences[i].lower()
        ):
            j += 1
        run = j - i + 1
        out.extend(sentences[i : j + 1] if run < limit else [sentences[i]])
        i = j + 1
    return " ".join(out) if out else text


@SpeechRegistry.register("faster-whisper")
class FasterWhisperBackend(SpeechBackend):
    """Local speech-to-text using Faster-Whisper (CTranslate2)."""

    backend_id = "faster-whisper"

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "float16",
        *,
        vad_filter: bool = False,
        hotwords: str = "",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        # Silero VAD drops silent stretches before decoding. Without it Whisper
        # can spend 10+ s on a silent clip, or invent text for it.
        self._vad_filter = vad_filter
        # Proper nouns the model should prefer when it hears something close
        # (e.g. "Nicx" instead of "Unix").
        self._hotwords = hotwords.strip()
        self._model: Optional[WhisperModel] = None
        self._last_error: Optional[str] = None
        self._idle = IdleRelease(self.unload, f"Whisper {model_size}")

    def _resolve_compute_type(self) -> str:
        """Pick a CTranslate2 compute type supported by the configured device."""
        if ctranslate2 is None:
            return self._compute_type

        try:
            supported = set(ctranslate2.get_supported_compute_types(self._device))
        except Exception as exc:
            logger.debug(
                "Could not inspect CTranslate2 compute types for %s: %s",
                self._device,
                exc,
            )
            return self._compute_type

        if self._compute_type in supported:
            return self._compute_type

        preferences = (
            ("int8", "float32", "int8_float32", "int16")
            if self._compute_type == "float16"
            else ("float32", "int8", "int8_float32", "int16")
        )
        fallback = next((value for value in preferences if value in supported), None)
        if fallback is None:
            return self._compute_type

        logger.warning(
            "CTranslate2 compute_type=%r is not supported on device=%r; "
            "using %r instead",
            self._compute_type,
            self._device,
            fallback,
        )
        return fallback

    def _ensure_model(self) -> WhisperModel:
        """Lazy-load the Whisper model on first use."""
        if self._model is None:
            if WhisperModel is None:
                self._last_error = (
                    "faster-whisper is not installed. "
                    "Install with: uv sync --extra desktop"
                )
                raise ImportError(self._last_error)
            compute_type = self._resolve_compute_type()
            options = dict(
                device=self._device,
                compute_type=compute_type,
                # CTranslate2 defaults to 4 threads; "small" with 8 was ~15%
                # faster here (12 cores), more brings little.
                cpu_threads=min(8, os.cpu_count() or 4),
            )
            try:
                # Recarregar depois do ócio não precisa consultar o Hugging Face.
                self._model = WhisperModel(
                    self._model_size, local_files_only=True, **options
                )
            except Exception:
                self._model = WhisperModel(self._model_size, **options)
        self._last_error = None
        return self._model

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio bytes using Faster-Whisper."""
        try:
            model = self._ensure_model()
            self._idle.touch()

            # Write audio to a temp file (faster-whisper needs a file path).
            # delete=False + manual unlink: on Windows an open
            # NamedTemporaryFile holds an exclusive handle, so PyAV's reopen
            # of tmp.name inside model.transcribe() fails with EACCES.
            suffix = f".{format}" if not format.startswith(".") else format
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            try:
                with tmp:
                    tmp.write(audio)

                # Each segment decoded on its own: carrying the previous text
                # over is what makes Whisper loop ("E aí? E aí? E aí?").
                kwargs: dict = {"condition_on_previous_text": False}
                if language:
                    kwargs["language"] = language
                if self._vad_filter:
                    kwargs["vad_filter"] = True
                if self._hotwords:
                    kwargs["hotwords"] = self._hotwords

                segments_iter, info = model.transcribe(tmp.name, **kwargs)
                segments_list = [s for s in segments_iter if not _likely_not_speech(s)]
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError as unlink_exc:
                    logger.debug(
                        "Could not remove temp audio file %s: %s",
                        tmp.name,
                        unlink_exc,
                    )
        except Exception as exc:
            self._last_error = str(exc)
            raise

        # Build result
        text = _collapse_repeats("".join(seg.text for seg in segments_list).strip())
        segments = [
            Segment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                confidence=None,
            )
            for seg in segments_list
        ]

        self._last_error = None
        return TranscriptionResult(
            text=text,
            language=getattr(info, "language", None),
            confidence=getattr(info, "language_probability", None),
            duration_seconds=getattr(info, "duration", 0.0),
            segments=segments,
        )

    def transcrever_array(
        self, audio: object, *, language: Optional[str] = None
    ) -> str:
        """Transcreve áudio float32 mono a 16 kHz direto da memória.

        Usado pelo ditado: nada vai para o disco (``transcribe`` precisa de um
        arquivo temporário). Mesmo modelo, mesmo descarregamento por ócio.
        """
        try:
            model = self._ensure_model()
            self._idle.touch()
            kwargs: dict = {"condition_on_previous_text": False}
            if language:
                kwargs["language"] = language
            if self._vad_filter:
                kwargs["vad_filter"] = True
            if self._hotwords:
                kwargs["hotwords"] = self._hotwords
            segments_iter, _info = model.transcribe(audio, **kwargs)
            partes = [s.text for s in segments_iter if not _likely_not_speech(s)]
        except Exception as exc:
            self._last_error = str(exc)
            raise
        self._last_error = None
        return _collapse_repeats("".join(partes).strip())

    def health(self) -> bool:
        """Check the package is installed, without loading the model.

        Loading here kept ~470 MB in RAM from the moment the server started,
        even when nobody used voice. The model loads on the first transcription.
        """
        if self._model is not None:
            return True
        if WhisperModel is None:
            self._last_error = (
                "O reconhecimento de voz (faster-whisper) não está instalado. "
                "Instale com: uv sync --extra desktop"
            )
            return False
        return True

    def unload(self) -> None:
        """Drop the model from memory; the next transcription loads it again."""
        self._model = None
        import gc

        gc.collect()

    def last_error(self) -> Optional[str]:
        """Return the last model load or transcription error, if any."""
        return self._last_error

    def supported_formats(self) -> List[str]:
        """Supported audio formats (same as ffmpeg/Whisper)."""
        return ["wav", "mp3", "m4a", "ogg", "flac", "webm"]
