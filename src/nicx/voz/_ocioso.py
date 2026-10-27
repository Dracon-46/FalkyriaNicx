"""Descarrega modelos de voz parados.

Whisper e Kokoro (com o torch) somam ~1 GB de RAM. Num PC de 16 GB que
também roda o modelo de linguagem, isso pesa à toa entre uma conversa por
voz e outra. Depois de alguns minutos sem uso o modelo sai da memória; o
próximo uso carrega de novo (poucos segundos).

``NICX_VOICE_IDLE_SECONDS`` muda o tempo (padrão 300 s); ``0`` nunca
descarrega.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_IDLE_SECONDS = 300.0


def idle_seconds() -> float:
    raw = os.environ.get("NICX_VOICE_IDLE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_IDLE_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_IDLE_SECONDS


class IdleRelease:
    """Chama ``release`` quando ``touch`` fica ``seconds`` sem ser chamado."""

    def __init__(
        self, release: Callable[[], None], name: str, seconds: Optional[float] = None
    ) -> None:
        self._release = release
        self._name = name
        self._seconds = idle_seconds() if seconds is None else seconds
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def touch(self) -> None:
        if self._seconds <= 0:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._seconds, self._fire)
            self._timer.daemon = True
            self._timer.name = f"descarga-{self._name}"
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        try:
            self._release()
            logger.info("%s descarregado da memória (parado)", self._name)
        except Exception as exc:  # pragma: no cover - limpeza é melhor esforço
            logger.debug("Falha ao descarregar %s: %s", self._name, exc)


__all__ = ["DEFAULT_IDLE_SECONDS", "IdleRelease", "idle_seconds"]
