"""Frase de ativação "Nicx, ligar": escuta local em segundo plano.

Pipeline, do mais barato ao mais caro:

1. o microfone entrega quadros de 32 ms (512 amostras a 16 kHz);
2. um portão de energia descarta o silêncio sem rodar modelo nenhum;
3. o Silero VAD (o mesmo ONNX que o faster-whisper já traz) confirma voz;
4. só quando uma fala curta termina (até ~3 s) o Whisper a transcreve, direto
   da memória (nada vai para o disco), e o texto é comparado com as frases
   de ativação, tolerando "Nix", "Nics", "Nick"...

Nenhum áudio é guardado e nada sai do computador. Este módulo não importa
numpy, sounddevice nem faster-whisper no topo: o comparador de frases e a
lógica de disparo são puros e testáveis sem eles.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # 32 ms: o tamanho de quadro do Silero VAD a 16 kHz
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE

DEFAULT_WAKE_PHRASES: tuple[str, ...] = (
    "Nicx, ligar",
    "Nicx, acordar",
    "Nicx, aparece",
    "Nicx, abrir",
    "Ei Nicx",
    "Oi Nicx",
)

# ---------------------------------------------------------------------------
# Comparação de frases
# ---------------------------------------------------------------------------

# Como o Whisper costuma escrever "Nicx": a chave fonética de cada grafia.
# nicx/nix/nics/nicks/niks/nyx -> "niks"; nick/nik -> "nik".
_NAME_KEYS = frozenset({"niks", "nik"})
# "Unix": o Whisper às vezes ouve assim; só vale com um comando logo depois.
_LOOSE_KEYS = frozenset({"uniks"})

_GREETINGS = frozenset({"ei", "ey", "hey", "oi", "ola", "alo", "o"})
# Palavras que podem aparecer entre o nome e o comando ("Nicx, pode ligar").
_INNER_FILLERS = frozenset({"pode", "por", "favor", "vai", "ja", "agora", "se"})
# Palavras que podem vir no fim ("Nicx, liga aí", "Oi Nicx, tudo bem").
_TRAILING_FILLERS = frozenset(
    {"ai", "ae", "ja", "agora", "por", "favor", "pra", "mim", "la", "logo", "ta"}
)
_MAX_TRAILING = 3
# Uma frase de ativação é curta; textos longos que citam o Nicx não contam.
_MAX_TOKENS = 7


def normalize_text(text: str) -> list[str]:
    """Minúsculas, sem acentos nem pontuação, separado em palavras."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", plain)


def phonetic_key(token: str) -> str:
    """Chave grosseira de pronúncia: nicx, nix, nics, nicks e niks viram "niks"."""
    key = token.lower()
    for old, new in (
        ("ph", "f"),
        ("ck", "k"),
        ("qu", "k"),
        ("x", "ks"),
        ("c", "k"),
        ("q", "k"),
        ("y", "i"),
        ("z", "s"),
        ("h", ""),
    ):
        key = key.replace(old, new)
    # "nikks" -> "niks"
    return re.sub(r"(.)\1+", r"\1", key)


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_name_token(token: str, *, loose: bool = False) -> bool:
    """True se *token* soa como "Nicx".

    ``loose`` aceita uma letra de diferença na chave ("neks", "niki"), o que só
    é seguro quando um comando vem logo depois ("Nicx, ligar").
    """
    key = phonetic_key(token)
    if key in _NAME_KEYS:
        return True
    if not loose:
        return False
    if key in _LOOSE_KEYS:
        return True
    return (
        len(key) >= 3
        and key[0] == "n"
        and any(_edit_distance(key, name) <= 1 for name in _NAME_KEYS)
    )


def _same_word(spoken: str, expected: str) -> bool:
    """Mesma palavra ou outra flexão do mesmo verbo (liga/ligar/ligue)."""
    if spoken == expected:
        return True
    if spoken in _GREETINGS and expected in _GREETINGS:
        return True
    common = 0
    for a, b in zip(spoken, expected):
        if a != b:
            break
        common += 1
    shortest = min(len(spoken), len(expected))
    return (
        shortest >= 3
        and common >= max(3, shortest - 1)
        and abs(len(spoken) - len(expected)) <= 3
    )


def _split_glued_name(tokens: list[str]) -> list[str]:
    """Separa o nome grudado no comando: "nicxabriro" -> ["nicx", "abriro"]."""
    out = []
    for token in tokens:
        out.extend(_split_token(token))
    return out


def _split_token(token: str) -> list[str]:
    # Prefere o nome exato ("nicx" + "abriro") ao aproximado ("nicxa" + "briro").
    for loose in (False, True):
        for size in (5, 4, 3):
            head, rest = token[:size], token[size:]
            if len(rest) >= 3 and is_name_token(head, loose=loose):
                return [head, rest]
    return [token]


@dataclass(frozen=True)
class _Pattern:
    phrase: str
    tokens: tuple[str, ...]  # "" marca a posição do nome

    @property
    def has_command(self) -> bool:
        return any(t and t not in _GREETINGS for t in self.tokens)

    @property
    def starts_with_greeting(self) -> bool:
        return bool(self.tokens) and self.tokens[0] in _GREETINGS


class WakePhraseMatcher:
    """Reconhece as frases de ativação em uma transcrição curta.

    Cada frase configurada vira um padrão de palavras em que o nome ("Nicx")
    casa por pronúncia. Aceita uma saudação antes ("Ei Nicx, liga"), "pode"
    entre o nome e o comando e até duas palavras de enchimento no fim
    ("liga aí"). Frases longas, ou em que o nome não abre a fala, não contam:
    "eu uso o Nix para ligar o servidor" não ativa.
    """

    def __init__(self, phrases: Iterable[str] = DEFAULT_WAKE_PHRASES) -> None:
        patterns = []
        for phrase in phrases:
            tokens = normalize_text(phrase)
            if not tokens:
                continue
            marked = tuple("" if is_name_token(t) else t for t in tokens)
            if "" not in marked:
                logger.warning("Frase de ativação sem o nome do Nicx: %r", phrase)
                continue
            patterns.append(_Pattern(phrase=phrase, tokens=marked))
        self._patterns = tuple(patterns)

    @property
    def phrases(self) -> tuple[str, ...]:
        return tuple(p.phrase for p in self._patterns)

    def match(self, text: str) -> Optional[str]:
        """Devolve a frase reconhecida em *text*, ou None."""
        tokens = normalize_text(text)
        if not tokens or len(tokens) > _MAX_TOKENS:
            return None
        candidates = [tokens]
        split = _split_glued_name(tokens)
        if split != tokens:
            candidates.append(split)
        for candidate in candidates:
            for pattern in self._patterns:
                if self._match_pattern(pattern, candidate):
                    return pattern.phrase
        return None

    @staticmethod
    def _match_pattern(pattern: _Pattern, tokens: list[str]) -> bool:
        spoken = list(tokens)
        # Saudação opcional antes do nome ("Ei Nicx, ligar").
        if not pattern.starts_with_greeting and spoken[0] in _GREETINGS:
            spoken = spoken[1:]
        loose = pattern.has_command
        i = 0  # posição em spoken
        for j, expected in enumerate(pattern.tokens):
            if expected != "" and j > 0:
                while i < len(spoken) and spoken[i] in _INNER_FILLERS:
                    if _same_word(spoken[i], expected):
                        break
                    i += 1
            if i >= len(spoken):
                return False
            word = spoken[i]
            if expected == "":
                if not is_name_token(word, loose=loose):
                    return False
            elif not _same_word(word, expected):
                return False
            i += 1
        rest = spoken[i:]
        return len(rest) <= _MAX_TRAILING and all(t in _TRAILING_FILLERS for t in rest)


# ---------------------------------------------------------------------------
# Disparo: pausa, ocupado e intervalo entre ativações
# ---------------------------------------------------------------------------


class WakeTrigger:
    """Decide se uma fala pode ser transcrita e se uma ativação pode disparar.

    Não dispara quando: a escuta foi pausada (ícone da bandeja), o Nicx está
    ocupado (conversa por voz ativa ou falando, informado pelo servidor; ou a
    janela do mascote ainda aberta) ou outra ativação aconteceu há pouco.
    """

    def __init__(
        self,
        *,
        cooldown_s: float = 6.0,
        is_busy: Callable[[], bool] = lambda: False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cooldown_s = cooldown_s
        self._is_busy = is_busy
        self._clock = clock
        self._paused = False
        self._quiet_until = 0.0
        self.fired = 0

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def hold(self, seconds: float) -> None:
        """Ignora a escuta por *seconds* (ex.: logo depois de a janela fechar)."""
        self._quiet_until = max(self._quiet_until, self._clock() + seconds)

    def in_cooldown(self) -> bool:
        return self._clock() < self._quiet_until

    def blocked(self) -> bool:
        """Checagem barata, a cada quadro: pausa ou intervalo."""
        return self._paused or self.in_cooldown()

    def busy(self) -> bool:
        try:
            return bool(self._is_busy())
        except Exception as exc:  # o servidor pode estar fora do ar
            logger.debug("Checagem de ocupado falhou: %s", exc)
            return False

    def should_transcribe(self) -> bool:
        """Checagem por fala detectada, antes de gastar CPU com o Whisper."""
        return not self.blocked() and not self.busy()

    def fire(self) -> bool:
        """Registra uma ativação; False se ela deve ser ignorada."""
        if self.blocked() or self.busy():
            return False
        self.fired += 1
        self.hold(self.cooldown_s)
        return True


# ---------------------------------------------------------------------------
# Detecção de fala (portão de energia + Silero VAD)
# ---------------------------------------------------------------------------


class StreamingSileroVad:
    """Silero VAD quadro a quadro, com estado, usando o ONNX do faster-whisper."""

    _CONTEXT = 64

    def __init__(self) -> None:
        import numpy as np
        from faster_whisper.vad import get_vad_model

        self._np = np
        self._session = get_vad_model().session
        self.reset()

    def reset(self) -> None:
        np = self._np
        self._h = np.zeros((1, 1, 128), dtype="float32")
        self._c = np.zeros((1, 1, 128), dtype="float32")
        self._context = np.zeros(self._CONTEXT, dtype="float32")

    def __call__(self, frame: Any) -> float:
        np = self._np
        x = np.concatenate([self._context, frame]).reshape(1, -1)
        out, self._h, self._c = self._session.run(
            None, {"input": x, "h": self._h, "c": self._c}
        )
        self._context = frame[-self._CONTEXT :]
        return float(out[0])


def frame_rms(frame: Any) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(np.square(frame, dtype="float32"))))


@dataclass
class SegmentDetectorConfig:
    start_prob: float = 0.5
    end_prob: float = 0.35
    end_silence_s: float = 0.5  # silêncio que encerra uma fala
    preroll_s: float = 0.3
    min_speech_s: float = 0.25
    max_speech_s: float = 3.0
    # Portão de energia: abaixo disso nem roda o VAD (~-48 dBFS).
    min_rms: float = 0.004
    noise_factor: float = 2.5


@dataclass
class DetectorStats:
    frames: int = 0
    vad_frames: int = 0
    segments: int = 0
    too_long: int = 0


class SegmentDetector:
    """Agrupa quadros em falas curtas; descarta silêncio e falas longas.

    ``push`` recebe quadros float32 de 512 amostras e devolve a fala (um array)
    quando ela termina, ou None. Falas acima de ``max_speech_s`` são ignoradas
    por inteiro: frase de ativação é curta.
    """

    def __init__(
        self,
        vad: Callable[[Any], float],
        config: Optional[SegmentDetectorConfig] = None,
        *,
        vad_reset: Optional[Callable[[], None]] = None,
    ) -> None:
        self.cfg = config or SegmentDetectorConfig()
        self._vad = vad
        self._vad_reset = vad_reset
        self.stats = DetectorStats()
        self._noise = self.cfg.min_rms
        self._preroll: deque = deque(
            maxlen=max(1, round(self.cfg.preroll_s / FRAME_SECONDS))
        )
        self._end_frames = max(1, round(self.cfg.end_silence_s / FRAME_SECONDS))
        self._max_frames = round(self.cfg.max_speech_s / FRAME_SECONDS)
        self._min_voiced = max(1, round(self.cfg.min_speech_s / FRAME_SECONDS))
        self._gated_run = 0
        self.reset()

    def reset(self) -> None:
        self._in_speech = False
        self._too_long = False
        self._frames: list = []
        self._voiced = 0
        self._silence = 0
        self._preroll.clear()

    def _probability(self, frame: Any) -> float:
        rms = frame_rms(frame)
        gate = max(self.cfg.min_rms, self._noise * self.cfg.noise_factor)
        if rms < gate and not self._in_speech:
            # Silêncio: acompanha o ruído de fundo e nem roda o VAD.
            self._noise = 0.95 * self._noise + 0.05 * max(rms, 1e-5)
            self._gated_run += 1
            if self._gated_run == 30 and self._vad_reset:  # ~1 s calado
                self._vad_reset()
            return 0.0
        self._gated_run = 0
        self.stats.vad_frames += 1
        return self._vad(frame)

    def push(self, frame: Any) -> Optional[Any]:
        self.stats.frames += 1
        prob = self._probability(frame)
        cfg = self.cfg
        if not self._in_speech:
            if prob >= cfg.start_prob:
                self._in_speech = True
                self._frames = list(self._preroll)
                self._frames.append(frame)
                self._voiced = 1
                self._silence = 0
                self._too_long = False
            else:
                self._preroll.append(frame)
            return None

        if not self._too_long:
            self._frames.append(frame)
        if prob >= cfg.end_prob:
            self._silence = 0
            if prob >= cfg.start_prob:
                self._voiced += 1
        else:
            self._silence += 1

        speech_frames = len(self._frames) - self._silence
        if not self._too_long and speech_frames > self._max_frames + len(self._preroll):
            # Longa demais para ser "Nicx, ligar": espera acabar e descarta.
            self._too_long = True
            self._frames = []

        if self._silence < self._end_frames:
            return None

        too_long, voiced, frames = self._too_long, self._voiced, self._frames
        self.reset()
        if too_long:
            self.stats.too_long += 1
            return None
        if voiced < self._min_voiced:
            return None
        import numpy as np

        # Mantém ~200 ms de silêncio no fim; o resto só atrasaria o Whisper.
        keep = len(frames) - max(0, self._end_frames - round(0.2 / FRAME_SECONDS))
        self.stats.segments += 1
        return np.concatenate(frames[:keep])


# ---------------------------------------------------------------------------
# Transcrição curta
# ---------------------------------------------------------------------------


class WakeTranscriber:
    """Whisper local para falas curtas, direto de um array (sem arquivo)."""

    def __init__(
        self,
        model_size: str = "base",
        *,
        language: str = "pt",
        hotwords: str = "Nicx",
        initial_prompt: str = "Nicx, ligar. Oi Nicx.",
        compute_type: str = "int8",
        cpu_threads: int = 4,
    ) -> None:
        self.model_size = model_size
        self.language = language or None
        self.hotwords = hotwords
        # Contexto que puxa o Whisper para o nome: no microfone do notebook o
        # base ouvia "Nix, rigor" e "Liga"; com ele acertou 5 de 5, sem falso
        # positivo nas outras falas gravadas.
        self.initial_prompt = initial_prompt
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                kwargs = {
                    "device": "cpu",
                    "compute_type": self.compute_type,
                    "cpu_threads": self.cpu_threads,
                }
                try:
                    # Modelo já baixado: não consulta a internet.
                    self._model = WhisperModel(
                        self.model_size, local_files_only=True, **kwargs
                    )
                except Exception:
                    logger.info("Baixando o Whisper %s (só desta vez)", self.model_size)
                    self._model = WhisperModel(self.model_size, **kwargs)

    def __call__(self, audio: Any) -> str:
        self.load()
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            hotwords=self.hotwords or None,
            initial_prompt=self.initial_prompt or None,
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=False,
            # Frase de ativação é curta: corta alucinações em laço
            # ("o que é o que é o que é...") em vez de transcrever 200 tokens.
            max_new_tokens=24,
            no_repeat_ngram_size=3,
        )
        return "".join(seg.text for seg in segments).strip()


# ---------------------------------------------------------------------------
# Fontes de áudio
# ---------------------------------------------------------------------------


class MicrophoneSource:
    """Quadros do microfone padrão via sounddevice (callback, sem laço ocupado)."""

    def __init__(self, *, device: Any = None, max_queue: int = 200) -> None:
        self._device = device
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._stream: Any = None
        self._resample: Optional[Callable[[Any], Any]] = None
        self._pending: Any = None

    def start(self) -> None:
        import numpy as np
        import sounddevice as sd

        def callback(indata, _frames, _time, status) -> None:  # noqa: ANN001
            if status:
                logger.debug("Microfone: %s", status)
            mono = indata[:, 0].copy()
            try:
                self._queue.put_nowait(mono)
            except queue.Full:
                pass  # o processamento atrasou: perder um quadro não importa

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=FRAME_SAMPLES,
                device=self._device,
                callback=callback,
            )
        except Exception:
            # Alguns microfones não aceitam 16 kHz: usa a taxa nativa e reamostra.
            info = sd.query_devices(self._device, "input")
            rate = int(info["default_samplerate"])
            block = int(FRAME_SAMPLES * rate / SAMPLE_RATE)
            src = np.arange(block)
            dst = np.linspace(0, block - 1, FRAME_SAMPLES)
            self._resample = lambda x: np.interp(dst, src, x).astype("float32")
            self._stream = sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype="float32",
                blocksize=block,
                device=self._device,
                callback=callback,
            )
        self._stream.start()

    def read(self, timeout: float = 0.5) -> Optional[Any]:
        try:
            frame = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        return self._resample(frame) if self._resample else frame

    def drain(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None


def iter_file_frames(path: str) -> Iterable[Any]:
    """Quadros de 512 amostras a 16 kHz de um arquivo de áudio (modo de teste)."""
    import numpy as np
    import soundfile as sf

    data, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if rate != SAMPLE_RATE:
        n = int(len(mono) * SAMPLE_RATE / rate)
        mono = np.interp(
            np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono
        ).astype("float32")
    # Silêncio no fim para a última fala terminar.
    mono = np.concatenate([mono, np.zeros(SAMPLE_RATE, dtype="float32")])
    for start in range(0, len(mono) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
        yield mono[start : start + FRAME_SAMPLES]


# ---------------------------------------------------------------------------
# O laço de escuta
# ---------------------------------------------------------------------------


@dataclass
class WakeEvent:
    phrase: str
    text: str
    speech_end: float  # time.time() do fim da fala
    transcribe_s: float


@dataclass
class SegmentResult:
    """O que aconteceu com uma fala (modo arquivo e registro)."""

    duration_s: float
    text: str = ""
    phrase: Optional[str] = None
    skipped: str = ""  # "ocupado", "pausado"...
    transcribe_s: float = 0.0
    fired: bool = False


@dataclass
class WakeListener:
    """Liga detector, transcritor, comparador e disparo."""

    detector: SegmentDetector
    transcribe: Callable[[Any], str]
    matcher: WakePhraseMatcher
    trigger: WakeTrigger
    on_wake: Callable[[WakeEvent], None] = lambda event: None
    on_segment: Callable[[SegmentResult], None] = lambda result: None
    _stop: threading.Event = field(default_factory=threading.Event)

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def feed(self, frame: Any) -> Optional[SegmentResult]:
        """Processa um quadro; devolve o resultado quando uma fala termina."""
        if self.trigger.blocked():
            # Pausado ou logo após uma ativação: nem o VAD roda.
            self.detector.reset()
            return None
        segment = self.detector.push(frame)
        if segment is None:
            return None
        speech_end = time.time()
        result = SegmentResult(duration_s=len(segment) / SAMPLE_RATE)
        if not self.trigger.should_transcribe():
            result.skipped = "ocupado"
            self.on_segment(result)
            return result
        started = time.perf_counter()
        try:
            result.text = self.transcribe(segment)
        except Exception as exc:
            logger.warning("Falha ao transcrever: %s", exc)
            result.skipped = "erro"
            self.on_segment(result)
            return result
        result.transcribe_s = time.perf_counter() - started
        result.phrase = self.matcher.match(result.text)
        if result.phrase and self.trigger.fire():
            result.fired = True
            self.on_wake(
                WakeEvent(
                    phrase=result.phrase,
                    text=result.text,
                    speech_end=speech_end,
                    transcribe_s=result.transcribe_s,
                )
            )
        self.on_segment(result)
        return result

    def run(self, source: MicrophoneSource) -> None:
        """Escuta até ``stop()``. Bloqueia; rode o ícone da bandeja em outra thread."""
        source.start()
        try:
            while not self._stop.is_set():
                frame = source.read(timeout=0.5)
                if frame is None:
                    continue
                result = self.feed(frame)
                if result is not None and result.transcribe_s:
                    # O áudio que chegou durante a transcrição é antigo: descarta.
                    source.drain()
        finally:
            source.stop()

    def run_frames(self, frames: Sequence[Any] | Iterable[Any]) -> list[SegmentResult]:
        results = []
        for frame in frames:
            result = self.feed(frame)
            if result is not None:
                results.append(result)
        return results


def build_listener(
    *,
    phrases: Iterable[str] = DEFAULT_WAKE_PHRASES,
    model_size: str = "base",
    language: str = "pt",
    hotwords: str = "Nicx",
    is_busy: Callable[[], bool] = lambda: False,
    max_speech_s: float = 3.0,
    on_wake: Callable[[WakeEvent], None] = lambda event: None,
    on_segment: Callable[[SegmentResult], None] = lambda result: None,
) -> WakeListener:
    """Monta o pipeline real (Silero + Whisper)."""
    vad = StreamingSileroVad()
    detector = SegmentDetector(
        vad, SegmentDetectorConfig(max_speech_s=max_speech_s), vad_reset=vad.reset
    )
    return WakeListener(
        detector=detector,
        transcribe=WakeTranscriber(model_size, language=language, hotwords=hotwords),
        matcher=WakePhraseMatcher(phrases),
        trigger=WakeTrigger(is_busy=is_busy),
        on_wake=on_wake,
        on_segment=on_segment,
    )


__all__ = [
    "DEFAULT_WAKE_PHRASES",
    "FRAME_SAMPLES",
    "SAMPLE_RATE",
    "MicrophoneSource",
    "SegmentDetector",
    "SegmentDetectorConfig",
    "SegmentResult",
    "StreamingSileroVad",
    "WakeEvent",
    "WakeListener",
    "WakePhraseMatcher",
    "WakeTranscriber",
    "WakeTrigger",
    "build_listener",
    "is_name_token",
    "iter_file_frames",
    "normalize_text",
    "phonetic_key",
]
