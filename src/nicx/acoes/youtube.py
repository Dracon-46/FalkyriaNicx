"""'Toca X no YouTube': abre direto o primeiro vídeo da busca.

Sem chave de API: lê a página de resultados do YouTube e pega o id do
primeiro vídeo. Se a página mudar ou a internet falhar, abre a busca.
A busca vai para o YouTube, como se a pessoa digitasse lá.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.youtube.com/results?search_query={}"
WATCH_URL = "https://www.youtube.com/watch?v={}"
_VIDEO_ID = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')


def search_url(query: str) -> str:
    return SEARCH_URL.format(quote_plus(query))


def first_video(query: str, timeout: float = 6.0) -> Optional[str]:
    """Endereço do primeiro vídeo da busca, ou None."""
    try:
        response = httpx.get(
            search_url(query),
            headers={
                "Accept-Language": "pt-BR,pt;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("Busca no YouTube falhou: %s", exc)
        return None
    match = _VIDEO_ID.search(response.text)
    return WATCH_URL.format(match.group(1)) if match else None


__all__ = ["first_video", "search_url"]
