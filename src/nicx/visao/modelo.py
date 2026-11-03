"""O modelo escolhido enxerga imagens? (Ollama: ``capabilities`` com "vision").

O ``qwen3.5`` enxerga (projetor de imagens embutido no próprio modelo), então
descrever uma imagem não exige outro modelo nem mais RAM. Outros motores ou
modelos sem visão recebem só o texto lido por OCR.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_CACHE: dict[tuple[str, str], bool] = {}


def _host(config: Any) -> str:
    from nicx.motores.ollama import OllamaEngine, _normalize_host

    ollama = getattr(getattr(config, "engine", None), "ollama", None)
    host = (
        getattr(ollama, "host", "")
        or os.environ.get("OLLAMA_HOST")
        or OllamaEngine._DEFAULT_HOST
    )
    return _normalize_host(host)


def enxerga(modelo: str, config: Any = None) -> bool:
    """True se *modelo* (no Ollama) aceita imagens. Na dúvida, False."""
    motor = getattr(getattr(config, "engine", None), "default", "ollama")
    if motor != "ollama" or not modelo:
        return False
    nome = modelo.removeprefix("ollama/")
    chave = (_host(config), nome)
    if chave in _CACHE:
        return _CACHE[chave]
    try:
        import httpx

        resposta = httpx.post(f"{chave[0]}/api/show", json={"model": nome}, timeout=5)
        resposta.raise_for_status()
        sim = "vision" in (resposta.json().get("capabilities") or [])
    except Exception as exc:  # noqa: BLE001 - o Ollama pode estar ligando: não guarda
        logger.debug("Visão do modelo não conferida: %s", type(exc).__name__)
        return False
    _CACHE[chave] = sim
    return sim


__all__ = ["enxerga"]
