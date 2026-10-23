"""Tests for Faster-Whisper speech backend."""

from unittest.mock import MagicMock, patch

import pytest

from nicx.core.registry import SpeechRegistry
from nicx.speech.faster_whisper import FasterWhisperBackend


@pytest.fixture(autouse=True)
def _register_faster_whisper():
    """Re-register after any registry clear."""
    if not SpeechRegistry.contains("faster-whisper"):
        SpeechRegistry.register_value("faster-whisper", FasterWhisperBackend)


def test_faster_whisper_backend_registers():
    """Backend registers itself in SpeechRegistry."""
    assert SpeechRegistry.contains("faster-whisper")


def test_faster_whisper_transcribe():
    """Transcribe returns a TranscriptionResult."""
    from nicx.speech._stubs import TranscriptionResult

    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = " Hello world"
    mock_segment.start = 0.0
    mock_segment.end = 1.2
    mock_segment.avg_logprob = -0.3

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.95
    mock_info.duration = 1.5

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        return_value=mock_model,
    ):
        from nicx.speech.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend(model_size="base", device="cpu")
        result = backend.transcribe(b"fake audio bytes")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.duration_seconds == 1.5


def test_faster_whisper_transcribe_temp_file_reopenable_and_removed():
    """The temp file must be closed before the model reads it, and gone after.

    On Windows, an open NamedTemporaryFile holds an exclusive handle, so
    PyAV's reopen of the path inside model.transcribe() fails with EACCES
    unless the file is closed first. Opening the path inside the mocked
    transcribe reproduces that failure mode on Windows.
    """
    import os

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.95
    mock_info.duration = 1.5

    seen = {}

    def fake_transcribe(path, **kwargs):
        seen["path"] = path
        with open(path, "rb") as fh:
            seen["content"] = fh.read()
        return iter(()), mock_info

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = fake_transcribe

    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        return_value=mock_model,
    ):
        backend = FasterWhisperBackend(model_size="base", device="cpu")
        backend.transcribe(b"fake audio bytes")

    assert seen["content"] == b"fake audio bytes"
    assert not os.path.exists(seen["path"])


def test_faster_whisper_transcribe_removes_temp_file_on_error():
    """The temp file is cleaned up even when transcription fails."""
    import os

    seen = {}

    def fake_transcribe(path, **kwargs):
        seen["path"] = path
        raise RuntimeError("decode failed")

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = fake_transcribe

    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        return_value=mock_model,
    ):
        backend = FasterWhisperBackend(model_size="base", device="cpu")
        with pytest.raises(RuntimeError, match="decode failed"):
            backend.transcribe(b"fake audio bytes")

    assert "path" in seen
    assert not os.path.exists(seen["path"])
    assert "decode failed" in (backend.last_error() or "")


def test_faster_whisper_falls_back_from_unsupported_float16():
    mock_model = MagicMock()

    with (
        patch(
            "nicx.speech.faster_whisper.WhisperModel",
            return_value=mock_model,
        ) as mock_whisper,
        patch(
            "nicx.speech.faster_whisper.ctranslate2",
            MagicMock(
                get_supported_compute_types=MagicMock(return_value={"float32", "int8"})
            ),
        ),
    ):
        backend = FasterWhisperBackend(
            model_size="base",
            device="cpu",
            compute_type="float16",
        )
        assert backend._ensure_model() is mock_model

    mock_whisper.assert_called_once_with("base", device="cpu", compute_type="int8")


def test_faster_whisper_missing_dependency_hint_uses_desktop_extra():
    with patch("nicx.speech.faster_whisper.WhisperModel", new=None):
        backend = FasterWhisperBackend()

        with pytest.raises(ImportError) as excinfo:
            backend._ensure_model()

    assert "uv sync --extra desktop" in str(excinfo.value)
    assert "uv sync --extra speech" not in str(excinfo.value)


def test_faster_whisper_health_no_model():
    """Health returns False before model is loaded."""
    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        new=None,
    ):
        backend = FasterWhisperBackend()
        assert backend.health() is False
        assert "uv sync --extra desktop" in (backend.last_error() or "")


def test_faster_whisper_health_captures_load_error():
    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        side_effect=RuntimeError("missing cublas64_12.dll"),
    ):
        backend = FasterWhisperBackend()
        assert backend.health() is False
        assert "missing cublas64_12.dll" in (backend.last_error() or "")


def test_faster_whisper_supported_formats():
    """Backend supports standard audio formats."""
    with patch("nicx.speech.faster_whisper.WhisperModel"):
        from nicx.speech.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend.__new__(FasterWhisperBackend)
        formats = backend.supported_formats()
        assert "wav" in formats
        assert "mp3" in formats
        assert "webm" in formats


def test_faster_whisper_forwards_vad_filter_and_hotwords():
    """VAD and hotwords reach the model only when configured."""
    mock_info = MagicMock(language="pt", language_probability=0.99, duration=2.0)
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter(()), mock_info)

    with patch(
        "nicx.speech.faster_whisper.WhisperModel",
        return_value=mock_model,
    ):
        plain = FasterWhisperBackend(model_size="base", device="cpu")
        plain.transcribe(b"audio", language="pt")
        assert mock_model.transcribe.call_args.kwargs == {
            "condition_on_previous_text": False,
            "language": "pt",
        }

        tuned = FasterWhisperBackend(
            model_size="base",
            device="cpu",
            vad_filter=True,
            hotwords=" Nicx Falkyria ",
        )
        tuned.transcribe(b"audio", language="pt")
        assert mock_model.transcribe.call_args.kwargs == {
            "condition_on_previous_text": False,
            "language": "pt",
            "vad_filter": True,
            "hotwords": "Nicx Falkyria",
        }


def test_discovery_passes_speech_config_to_faster_whisper():
    from nicx.core.config import NicxConfig
    from nicx.speech._discovery import _create_backend

    cfg = NicxConfig()
    backend = _create_backend("faster-whisper", cfg)

    assert isinstance(backend, FasterWhisperBackend)
    assert backend._compute_type == "int8"
    assert backend._vad_filter is True
    assert backend._hotwords == cfg.speech.hotwords


def test_collapse_repeats_keeps_one_copy_of_a_loop():
    from nicx.speech.faster_whisper import _collapse_repeats

    assert _collapse_repeats("E aí? E aí? E aí?") == "E aí?"
    assert (
        _collapse_repeats("Oi. Tudo bem? tudo bem? Tudo bem? Fim.")
        == "Oi. Tudo bem? Fim."
    )
    # Two in a row can be on purpose.
    assert _collapse_repeats("Sim. Sim.") == "Sim. Sim."
    assert _collapse_repeats("não, não, não") == "não, não, não"
    assert _collapse_repeats("") == ""


def test_faster_whisper_drops_segments_made_up_from_noise():
    def seg(text, no_speech, logprob):
        return MagicMock(
            text=text, start=0.0, end=1.0, no_speech_prob=no_speech, avg_logprob=logprob
        )

    mock_info = MagicMock(language="pt", language_probability=0.9, duration=3.0)
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        iter([seg(" Nicx, que horas são?", 0.05, -0.3), seg(" E aí?", 0.8, -1.4)]),
        mock_info,
    )
    with patch("nicx.speech.faster_whisper.WhisperModel", return_value=mock_model):
        result = FasterWhisperBackend(model_size="base", device="cpu").transcribe(
            b"audio"
        )
    assert result.text == "Nicx, que horas são?"
    assert len(result.segments) == 1
