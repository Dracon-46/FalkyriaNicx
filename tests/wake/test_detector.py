"""Testes do "Nicx, ligar": frases, detecção de fala, disparo e pausa."""

from __future__ import annotations

import numpy as np
import pytest

from nicx.wake.detector import (
    DEFAULT_WAKE_PHRASES,
    FRAME_SAMPLES,
    SAMPLE_RATE,
    SegmentDetector,
    SegmentDetectorConfig,
    WakeListener,
    WakePhraseMatcher,
    WakeTrigger,
    is_name_token,
    normalize_text,
    phonetic_key,
)

# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------


@pytest.fixture
def matcher() -> WakePhraseMatcher:
    return WakePhraseMatcher()


@pytest.mark.parametrize(
    "text",
    [
        "Nicx, ligar.",
        "Nicx ligar",
        "Nix, ligar!",
        "Nics, liga aí",
        "Nick, liga aí por favor",
        "Nicks, ligar.",
        "NECX LIGAÍ",  # transcrição real do Whisper base
        "Nicxabriro",  # idem: nome grudado no comando
        "Nixligar",
        "Ei Nicx, ligar",
        "Nicx, pode ligar",
        "Nicx, acordar",
        "Nics acorda",
        "Nicx, aparece.",
        "Nicx, apareça!",
        "Nicx abrir",
        "Nicx, abre",
        "Ei, Nicx!",
        "Hey Nicx",
        "Oi Nicx!",
        "Oi, Nix.",
        "Unix, ligar",  # o Whisper às vezes ouve "Unix"
    ],
)
def test_wake_phrases_and_variants_match(matcher: WakePhraseMatcher, text: str) -> None:
    assert matcher.match(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Nicx",
        "Ligar Nicx",
        "Eu instalei o Unix no servidor ontem.",
        "O gerenciador de pacotes Nix é bom.",
        "O gerenciador de pacotes Nicx é bom.",
        "eu uso nix pra ligar o servidor",
        "Pode ligar a luz da sala?",
        "O Nick vai abrir a loja amanhã.",
        "Unic vai abrir a loja amanhã.",
        "Oi, tudo bem com você?",
        "Ei Nicx, tudo bem?",
        "Que horas são agora?",
        "Six, ligar",
        "Mix ligar",
        "Unix",
        "oi nicotina",
        "Ontem eu falei com o Nicx sobre ligar o computador mais cedo",
        "Obrigado.",  # alucinação típica do Whisper no silêncio
        "Legendas pela comunidade Amara.org",
    ],
)
def test_other_sentences_do_not_match(matcher: WakePhraseMatcher, text: str) -> None:
    assert matcher.match(text) is None


def test_match_returns_the_configured_phrase(matcher: WakePhraseMatcher) -> None:
    assert matcher.match("Nix, liga") == "Nicx, ligar"
    assert matcher.match("Nicx acordar") == "Nicx, acordar"


def test_custom_phrases() -> None:
    m = WakePhraseMatcher(["Bom dia Nicx", "sem o nome"])
    assert m.phrases == ("Bom dia Nicx",)  # frase sem o nome é ignorada
    assert m.match("Bom dia, Nix!") == "Bom dia Nicx"
    assert m.match("Nicx, ligar") is None


def test_default_phrases_cover_the_requested_variants() -> None:
    assert "Nicx, ligar" in DEFAULT_WAKE_PHRASES
    assert {"Ei Nicx", "Oi Nicx"} <= set(DEFAULT_WAKE_PHRASES)


def test_normalize_and_phonetics() -> None:
    assert normalize_text("Nicx, LIGA AÍ!") == ["nicx", "liga", "ai"]
    for spelling in ("nicx", "nix", "nics", "nicks", "niks", "nyx"):
        assert phonetic_key(spelling) == "niks"
    assert is_name_token("Nick")
    assert not is_name_token("neks")
    assert is_name_token("neks", loose=True)
    assert not is_name_token("mix", loose=True)


def test_config_default_phrases_match_module_defaults() -> None:
    from nicx.core.config import SpeechConfig

    cfg = SpeechConfig()
    assert cfg.wake_word is False  # opt-in
    assert tuple(cfg.wake_phrases) == DEFAULT_WAKE_PHRASES
    assert cfg.wake_model == "base"


# ---------------------------------------------------------------------------
# Disparo, intervalo e pausa
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_trigger_cooldown() -> None:
    clock = FakeClock()
    trigger = WakeTrigger(cooldown_s=6.0, clock=clock)
    assert trigger.fire() is True
    assert trigger.blocked()
    assert trigger.fire() is False
    clock.now += 5.9
    assert not trigger.should_transcribe()
    clock.now += 0.2
    assert trigger.should_transcribe()
    assert trigger.fire() is True
    assert trigger.fired == 2


def test_trigger_pause_and_resume() -> None:
    trigger = WakeTrigger(clock=FakeClock())
    trigger.pause()
    assert trigger.paused and trigger.blocked()
    assert trigger.fire() is False
    trigger.resume()
    assert trigger.fire() is True


def test_trigger_busy_flag_blocks() -> None:
    busy = {"value": True}
    trigger = WakeTrigger(is_busy=lambda: busy["value"], clock=FakeClock())
    assert not trigger.should_transcribe()
    assert trigger.fire() is False
    busy["value"] = False
    assert trigger.fire() is True


def test_trigger_busy_check_failure_is_not_busy() -> None:
    def broken() -> bool:
        raise OSError("servidor fora do ar")

    trigger = WakeTrigger(is_busy=broken, clock=FakeClock())
    assert trigger.should_transcribe()


def test_trigger_hold_after_window_closes() -> None:
    clock = FakeClock()
    trigger = WakeTrigger(clock=clock)
    trigger.hold(3.0)
    assert trigger.blocked()
    clock.now += 3.1
    assert not trigger.blocked()


# ---------------------------------------------------------------------------
# Detector de falas (VAD falso: o quadro "diz" se é voz)
# ---------------------------------------------------------------------------

SPEECH = np.full(FRAME_SAMPLES, 0.1, dtype="float32")
SILENCE = np.zeros(FRAME_SAMPLES, dtype="float32")


def _fake_vad(frame: np.ndarray) -> float:
    return 0.9 if float(np.abs(frame).mean()) > 0.05 else 0.05


def _frames(seconds: float, frame: np.ndarray) -> list[np.ndarray]:
    return [frame] * round(seconds * SAMPLE_RATE / FRAME_SAMPLES)


def _run(detector: SegmentDetector, frames: list[np.ndarray]) -> list[np.ndarray]:
    return [seg for f in frames if (seg := detector.push(f)) is not None]


def test_detector_emits_short_utterance() -> None:
    detector = SegmentDetector(_fake_vad)
    segments = _run(
        detector, _frames(1, SILENCE) + _frames(1.2, SPEECH) + _frames(1, SILENCE)
    )
    assert len(segments) == 1
    seconds = len(segments[0]) / SAMPLE_RATE
    assert 1.2 <= seconds <= 1.2 + 0.3 + 0.25  # fala + pré-rolagem + rabo


def test_detector_ignores_long_speech() -> None:
    detector = SegmentDetector(_fake_vad, SegmentDetectorConfig(max_speech_s=3.0))
    segments = _run(detector, _frames(5, SPEECH) + _frames(1, SILENCE))
    assert segments == []
    assert detector.stats.too_long == 1
    # E volta ao normal logo depois.
    assert len(_run(detector, _frames(1, SPEECH) + _frames(1, SILENCE))) == 1


def test_detector_ignores_clicks() -> None:
    detector = SegmentDetector(_fake_vad)
    assert _run(detector, _frames(0.1, SPEECH) + _frames(1, SILENCE)) == []


def test_detector_skips_vad_on_silence() -> None:
    calls = []

    def vad(frame: np.ndarray) -> float:
        calls.append(1)
        return 0.0

    detector = SegmentDetector(vad)
    _run(detector, _frames(3, SILENCE))
    assert calls == []  # o portão de energia nem chamou o modelo


def test_detector_short_pause_keeps_one_utterance() -> None:
    # "Nicx, [pausa da vírgula] ligar" é uma fala só.
    detector = SegmentDetector(_fake_vad)
    frames = _frames(0.5, SPEECH) + _frames(0.25, SILENCE) + _frames(0.6, SPEECH)
    segments = _run(detector, frames + _frames(1, SILENCE))
    assert len(segments) == 1


# ---------------------------------------------------------------------------
# O laço inteiro, com transcrição falsa
# ---------------------------------------------------------------------------


def _listener(texts: list[str], *, busy: bool = False) -> tuple[WakeListener, list]:
    woke: list = []
    heard = iter(texts)
    listener = WakeListener(
        detector=SegmentDetector(_fake_vad),
        transcribe=lambda audio: next(heard),
        matcher=WakePhraseMatcher(),
        trigger=WakeTrigger(is_busy=lambda: busy),
        on_wake=woke.append,
    )
    return listener, woke


def _utterance() -> list[np.ndarray]:
    return _frames(1.0, SPEECH) + _frames(1.0, SILENCE)


def test_listener_wakes_on_phrase() -> None:
    listener, woke = _listener(["Que horas são?", "Nix, ligar."])
    results = listener.run_frames(_utterance() + _utterance())
    assert [r.fired for r in results] == [False, True]
    assert len(woke) == 1
    assert woke[0].phrase == "Nicx, ligar"
    assert woke[0].text == "Nix, ligar."


def test_listener_cooldown_after_wake() -> None:
    listener, woke = _listener(["Nicx, ligar", "Nicx, ligar"])
    listener.run_frames(_utterance() + _utterance())
    # A segunda frase caiu no intervalo: nem foi transcrita.
    assert len(woke) == 1


def test_listener_does_not_transcribe_while_busy() -> None:
    transcribed = []
    listener = WakeListener(
        detector=SegmentDetector(_fake_vad),
        transcribe=lambda audio: transcribed.append(audio) or "Nicx, ligar",
        matcher=WakePhraseMatcher(),
        trigger=WakeTrigger(is_busy=lambda: True),
    )
    results = listener.run_frames(_utterance())
    assert [r.skipped for r in results] == ["ocupado"]
    assert transcribed == []


def test_listener_paused_skips_everything() -> None:
    listener, woke = _listener(["Nicx, ligar"])
    listener.trigger.pause()
    assert listener.run_frames(_utterance()) == []
    assert woke == []


def test_listener_survives_transcription_errors() -> None:
    def boom(audio: np.ndarray) -> str:
        raise RuntimeError("modelo indisponível")

    listener = WakeListener(
        detector=SegmentDetector(_fake_vad),
        transcribe=boom,
        matcher=WakePhraseMatcher(),
        trigger=WakeTrigger(),
    )
    assert [r.skipped for r in listener.run_frames(_utterance())] == ["erro"]
