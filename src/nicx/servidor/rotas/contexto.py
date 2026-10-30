"""Rotas do contexto da tela (``/v1/contexto``).

- ``GET /v1/contexto/config``: ``[contexto]`` atual e se o PC suporta.
- ``PUT /v1/contexto/config``: liga/desliga, "copiar a seleção" e o limite
  de caracteres (grava no config.toml e já vale para o servidor).

O conteúdo da área de transferência ou da janela nunca passa por aqui.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/contexto", tags=["contexto"])

LIMITES = (5000, 10000, 20000, 40000)


class ContextoUpdate(BaseModel):
    ativo: Optional[bool] = None
    copiar_selecao: Optional[bool] = None
    max_caracteres: Optional[int] = Field(default=None, ge=1000, le=200_000)


def _cfg(request: Request) -> Any:
    config = getattr(request.app.state, "config", None)
    cfg = getattr(config, "contexto", None)
    if cfg is None:
        from nicx.nucleo.config import ContextoConfig

        cfg = ContextoConfig()
    return cfg


def _status(cfg: Any) -> dict:
    return {
        "ativo": bool(cfg.ativo),
        "copiar_selecao": bool(cfg.copiar_selecao),
        "max_caracteres": int(cfg.max_caracteres),
        "limites": list(LIMITES),
        "suportado": sys.platform == "win32",
    }


def _config_path(request: Request):
    config = getattr(request.app.state, "config", None)
    path = getattr(config, "_config_path", None)
    if path is None:
        from nicx.nucleo.paths import get_config_path

        path = get_config_path()
    return path


def salvar(path, valores: dict) -> None:
    """Grava ``[contexto]`` no config.toml, preservando o resto."""
    import tomlkit

    if path.exists():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = tomlkit.document()
    if "contexto" not in doc:
        doc.add("contexto", tomlkit.table())
    for chave, valor in valores.items():
        doc["contexto"][chave] = valor
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _atualizar_config_em_cache(valores: dict) -> None:
    """A ferramenta ``contexto`` lê ``load_config()``: vale lá também."""
    try:
        from nicx.nucleo.config import load_config

        cache = load_config().contexto
        for chave, valor in valores.items():
            setattr(cache, chave, valor)
    except Exception:  # noqa: BLE001 - o arquivo já está gravado
        logger.debug("Config em memória não atualizada", exc_info=True)


@router.get("/config")
async def contexto_config(request: Request):
    return _status(_cfg(request))


@router.put("/config")
async def contexto_update(request: Request, body: ContextoUpdate):
    valores = body.model_dump(exclude_none=True)
    cfg = _cfg(request)
    if valores:
        await asyncio.to_thread(salvar, _config_path(request), valores)
        for chave, valor in valores.items():
            setattr(cfg, chave, valor)
        _atualizar_config_em_cache(valores)
        if "ativo" in valores:
            from nicx.contexto import janela

            if cfg.ativo:
                await asyncio.to_thread(janela.iniciar_rastreador)
            else:
                await asyncio.to_thread(janela.parar_rastreador)
    return _status(cfg)


__all__ = ["router", "salvar"]
