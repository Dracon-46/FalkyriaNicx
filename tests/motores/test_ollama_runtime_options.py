"""Tests for Ollama runtime option wiring (num_ctx / num_gpu)."""

from __future__ import annotations

from nicx.motores.ollama import _ollama_request_options


def test_with_explicit_runtime_kwargs() -> None:
    opts = _ollama_request_options(
        temperature=0.5,
        max_tokens=512,
        kwargs={"num_ctx": 64000, "num_gpu": 12},
    )
    assert opts["num_ctx"] == 64000
    assert opts["num_gpu"] == 12


def test_default_num_ctx_when_omitted(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("NICX_NUM_CTX", "24576")
    opts = _ollama_request_options(
        temperature=0.7,
        max_tokens=1024,
        kwargs={},
    )
    assert opts["num_ctx"] == 24576
    assert "num_gpu" not in opts


def test_default_num_ctx_comes_from_config(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    """``[engine.ollama] num_ctx`` sets the default; NICX_NUM_CTX still wins."""
    from nicx.motores.ollama import _default_num_ctx
    from nicx.nucleo.config import load_config

    cfg = tmp_path / "config.toml"
    cfg.write_text("[engine.ollama]\nnum_ctx = 4096\n", encoding="utf-8")
    monkeypatch.setenv("NICX_CONFIG", str(cfg))
    monkeypatch.delenv("NICX_NUM_CTX", raising=False)
    load_config.cache_clear()

    assert _default_num_ctx() == 4096
    opts = _ollama_request_options(temperature=0.7, max_tokens=64, kwargs={})
    assert opts["num_ctx"] == 4096

    monkeypatch.setenv("NICX_NUM_CTX", "2048")
    assert _default_num_ctx() == 2048


def test_invalid_config_num_ctx_falls_back(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    from nicx.motores.ollama import _default_num_ctx
    from nicx.nucleo.config import load_config

    cfg = tmp_path / "config.toml"
    cfg.write_text("[engine.ollama]\nnum_ctx = 0\n", encoding="utf-8")
    monkeypatch.setenv("NICX_CONFIG", str(cfg))
    monkeypatch.delenv("NICX_NUM_CTX", raising=False)
    load_config.cache_clear()

    assert _default_num_ctx() == 8192
