"""Tests for speech configuration."""

from nicx.core.config import NicxConfig, SpeechConfig


def test_speech_config_defaults():
    """Defaults target Brazilian Portuguese on a CPU-only machine."""
    cfg = SpeechConfig()
    assert cfg.backend == "auto"
    assert cfg.model == "small"
    assert cfg.language == "pt"
    assert cfg.device == "auto"
    assert cfg.compute_type == "int8"
    assert cfg.vad_filter is True
    assert "Nicx" in cfg.hotwords
    assert cfg.tts_backend == "kokoro"
    # Kokoro's Brazilian Portuguese voices start with "p".
    assert cfg.voice_id == "pf_dora"


def test_nicx_config_has_speech():
    cfg = NicxConfig()
    assert hasattr(cfg, "speech")
    assert isinstance(cfg.speech, SpeechConfig)
    assert cfg.speech.backend == "auto"


def test_nicx_system_has_speech_backend():
    """NicxSystem has a speech_backend attribute."""
    from nicx.system import NicxSystem

    assert "speech_backend" in NicxSystem.__dataclass_fields__
