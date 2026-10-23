"""Voice-ID selection for chat TTS.

Voice IDs are not portable between backends. These tests pin the rule that a
configured voice is only ever handed to the backend it belongs to, so a Kokoro
ID like ``bm_george`` can never reach OpenAI or Cartesia on fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from nicx.cli._voice_chat import _BACKEND_DEFAULT_VOICE, VoiceSession


@dataclass
class _Speech:
    tts_backend: str = "kokoro"
    voice_id: str = "bm_george"
    voice_speed: float = 1.0


@dataclass
class _Config:
    speech: _Speech


class _Backend:
    def __init__(self, backend_id: str) -> None:
        self.backend_id = backend_id


def _session(**kwargs) -> VoiceSession:
    return VoiceSession(config=_Config(speech=_Speech(**kwargs)))


def test_configured_voice_used_for_its_own_backend():
    voice_id, speed = _session().voice_for_backend(_Backend("kokoro"))
    assert voice_id == "bm_george"
    assert speed == 1.0


@pytest.mark.parametrize("other", ["openai_tts", "cartesia", "unknown"])
def test_kokoro_voice_never_leaks_to_other_backends(other):
    voice_id, _ = _session().voice_for_backend(_Backend(other))
    assert voice_id != "bm_george"
    assert voice_id == _BACKEND_DEFAULT_VOICE.get(other, "")


def test_openai_fallback_gets_a_voice_openai_accepts():
    from nicx.speech.openai_tts import OpenAITTSBackend

    voice_id, _ = _session().voice_for_backend(_Backend("openai_tts"))
    assert voice_id in OpenAITTSBackend.__dict__["available_voices"](
        OpenAITTSBackend.__new__(OpenAITTSBackend)
    )


def test_cartesia_voice_routes_back_to_cartesia_only():
    session = _session(tts_backend="cartesia", voice_id="a-cartesia-uuid")
    assert session.voice_for_backend(_Backend("cartesia"))[0] == "a-cartesia-uuid"
    # ...and must not be handed to Kokoro, which would mis-map its lang code.
    assert session.voice_for_backend(_Backend("kokoro"))[0] == "pf_dora"


def test_zero_speed_is_not_silently_rewritten():
    assert _session(voice_speed=0.0).get_voice_preferences()[2] == 0.0


def test_warning_emitted_once_per_backend():
    printed: list[str] = []

    class _Console:
        def print(self, msg):
            printed.append(str(msg))

    session, console = _session(), _Console()
    for _ in range(3):
        session.voice_for_backend(_Backend("openai_tts"), console)
    assert len(printed) == 1


@pytest.mark.parametrize("preferred", ["kokoro", "openai_tts", "cartesia"])
def test_configured_backend_is_tried_before_healthy_fallbacks(monkeypatch, preferred):
    import nicx.speech  # noqa: F401
    from nicx.core.registry import TTSRegistry

    checked = []

    class HealthyBackend(_Backend):
        def health(self):
            checked.append(self.backend_id)
            return True

    monkeypatch.setattr(TTSRegistry, "contains", lambda key: True)
    monkeypatch.setattr(TTSRegistry, "get", lambda key: lambda: HealthyBackend(key))
    session = _session(tts_backend=preferred, voice_id="chosen-voice")

    selected = session.get_tts_backend()

    assert selected.backend_id == preferred
    assert session.get_tts_backend() is selected
    assert checked == [preferred]
    assert session.voice_for_backend(selected) == ("chosen-voice", 1.0)


def test_synthesis_failure_falls_back_without_retrying_or_leaking_voice(monkeypatch):
    import nicx.speech  # noqa: F401
    from nicx.cli._voice_chat import speak
    from nicx.core.registry import TTSRegistry
    from nicx.speech.tts import TTSResult

    checked, spoken, played = [], [], []

    class Backend(_Backend):
        def health(self):
            checked.append(self.backend_id)
            return True

        def synthesize(self, text, **kwargs):
            spoken.append((self.backend_id, kwargs["voice_id"]))
            if self.backend_id == "openai_tts":
                raise RuntimeError("provider unavailable")
            return TTSResult(audio=b"wav", sample_rate=24000, format="wav")

    class Console:
        def print(self, message):
            pass

    monkeypatch.setattr(TTSRegistry, "contains", lambda key: True)
    monkeypatch.setattr(TTSRegistry, "get", lambda key: lambda: Backend(key))
    monkeypatch.setattr(
        "nicx.speech.voice_io.play_wav",
        lambda audio, **kwargs: played.append(audio),
    )
    session = _session(tts_backend="openai_tts", voice_id="nova")

    speak("First reply", Console(), session)
    speak("Second reply", Console(), session)

    assert checked == ["openai_tts", "kokoro"]
    assert spoken == [
        ("openai_tts", "nova"),
        ("kokoro", "pf_dora"),
        ("kokoro", "pf_dora"),
    ]
    assert played == [b"wav", b"wav"]


def test_prewarm_loads_backends_once_in_the_background(monkeypatch):
    import threading

    import nicx.speech._discovery as stt_discovery
    import nicx.speech._tts_discovery as tts_discovery

    release = threading.Event()
    calls = {"stt": 0, "tts": 0}

    def slow_stt(config):
        calls["stt"] += 1
        return _Backend("faster-whisper")

    def slow_tts(preferred, *, attempted=None):
        calls["tts"] += 1
        release.wait(5)
        return _Backend(preferred)

    monkeypatch.setattr(stt_discovery, "get_speech_backend", slow_stt)
    monkeypatch.setattr(tts_discovery, "get_tts_backend", slow_tts)

    session = _session()
    session.prewarm()
    # The chat loop asking meanwhile waits for the same load, not a second one.
    waiter = threading.Thread(target=session.get_tts_backend)
    waiter.start()
    release.set()
    waiter.join(5)

    assert session.get_tts_backend().backend_id == "kokoro"
    assert session.get_stt_backend().backend_id == "faster-whisper"
    assert calls == {"stt": 1, "tts": 1}
