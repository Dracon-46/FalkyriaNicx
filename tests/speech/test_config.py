"""Tests for speech configuration."""

from nicx.core.config import NicxConfig, SpeechConfig


def test_speech_config_defaults():
    cfg = SpeechConfig()
    assert cfg.backend == "auto"
    assert cfg.model == "base"
    assert cfg.language == ""
    assert cfg.device == "auto"
    assert cfg.compute_type == "float16"


def test_nicx_config_has_speech():
    cfg = NicxConfig()
    assert hasattr(cfg, "speech")
    assert isinstance(cfg.speech, SpeechConfig)
    assert cfg.speech.backend == "auto"


def test_nicx_system_has_speech_backend():
    """NicxSystem has a speech_backend attribute."""
    from nicx.system import NicxSystem

    assert "speech_backend" in NicxSystem.__dataclass_fields__
