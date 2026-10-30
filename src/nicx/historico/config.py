"""Leitura da seção ``[historico]`` com padrões seguros se a config falhar."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _cfg():
    try:
        from nicx.nucleo.config import load_config

        return load_config().historico
    except Exception:  # noqa: BLE001
        logger.debug("Config do histórico ilegível", exc_info=True)
        return None


def ligado() -> bool:
    c = _cfg()
    return True if c is None else bool(c.ligado)


def guardar_conversas() -> bool:
    c = _cfg()
    return True if c is None else bool(c.guardar_conversas)


def dias() -> int:
    c = _cfg()
    return 180 if c is None else int(c.dias)
