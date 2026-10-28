"""Informações de saúde do servidor do Nicx para o painel (com consentimento).

- ``server_started``: com que motor e família de modelo o servidor abriu, se
  o Ollama teve de ser ligado pelo Nicx, quais recursos de voz estão ligados,
  quanto tempo levou para abrir e o tamanho da máquina (RAM e núcleos).
- ``server_health``: a cada hora, quanta memória o Nicx usa e como estão a
  RAM e o processador do PC.

Nada que identifique a pessoa: só contagens e nomes de recursos.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

_MODEL_FAMILY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_STARTED_AT = time.monotonic()


def model_family(model: str) -> str | None:
    """'qwen3.5:4b' -> 'qwen3.5'. Nomes fora do padrão não vão."""
    family = (model or "").strip().lower().split(":", 1)[0].split("/")[-1]
    return family if _MODEL_FAMILY.match(family) else None


def _machine() -> dict[str, int]:
    try:
        import os

        import psutil

        return {
            "ram_gb": round(psutil.virtual_memory().total / 1024**3),
            "cpu_cores": os.cpu_count() or 0,
        }
    except Exception:
        return {}


def server_started_properties(
    *,
    engine: str,
    model: str,
    engine_autostarted: bool,
    voice_input: bool,
    voice_output: bool,
    wake_word: bool,
    quick_actions: bool,
    startup_ms: int,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "engine": engine,
        "engine_autostarted": engine_autostarted,
        "voice_input": voice_input,
        "voice_output": voice_output,
        "wake_word": wake_word,
        "quick_actions": quick_actions,
        "startup_ms": max(0, int(startup_ms)),
        **_machine(),
    }
    family = model_family(model)
    if family:
        props["model_family"] = family
    return props


def health_properties() -> dict[str, Any]:
    """Memória do Nicx, RAM e processador do PC, tempo ligado."""
    import psutil

    process = psutil.Process()
    return {
        "rss_mb": int(process.memory_info().rss / 1024**2),
        "ram_percent": int(psutil.virtual_memory().percent),
        "cpu_percent": int(psutil.cpu_percent(interval=None)),
        "uptime_min": int((time.monotonic() - _STARTED_AT) / 60),
    }


class HealthReporter:
    """Manda ``server_health`` a cada ``interval`` segundos enquanto o servidor roda."""

    def __init__(
        self, capture: Callable[[str, dict[str, Any]], None], interval: float = 3600.0
    ) -> None:
        self._capture = capture
        self._interval = interval
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="nicx-saude", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stopped.wait(self._interval):
            try:
                self._capture("server_health", health_properties())
            except Exception as exc:
                logger.debug("Saúde do servidor não enviada: %s", exc)

    def stop(self) -> None:
        self._stopped.set()


__all__ = [
    "HealthReporter",
    "health_properties",
    "model_family",
    "server_started_properties",
]
