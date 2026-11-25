"""Captura rápida para as notas (``/v1/captura``).

- ``GET /v1/captura``: ``[captura]`` e o estado do atalho.
- ``PUT /v1/captura`` (``ativo``, ``teclas``): grava no config.toml e
  reinicia o atalho na hora. Não pode repetir o atalho do Nicx nem o do ditado.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nicx.atalho.servico import rotulo_de, salvar_secao
from nicx.atalho.teclas import CombinacaoInvalida, normalizar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/captura", tags=["captura"])

_lock = threading.Lock()


class CapturaUpdate(BaseModel):
    ativo: Optional[bool] = None
    teclas: Optional[str] = Field(default=None, max_length=64)


def _config(request: Request) -> Any:
    config = getattr(request.app.state, "config", None)
    if config is None:
        from nicx.nucleo.config import load_config

        config = load_config()
        request.app.state.config = config
    return config


def gerenciador(request: Request) -> Any:
    atual = getattr(request.app.state, "captura", None)
    if atual is None:
        from nicx.captura.servico import gerenciador as novo

        atual = novo()
        request.app.state.captura = atual
    return atual


def _forma(teclas: str) -> str:
    try:
        return normalizar(teclas)
    except CombinacaoInvalida:
        return str(teclas or "").strip().lower()


def _status(request: Request) -> dict:
    cfg = _config(request).captura
    return {
        "ativo": bool(cfg.ativo),
        "teclas": cfg.teclas,
        "rotulo": rotulo_de(cfg.teclas),
        **gerenciador(request).status(),
    }


@router.get("")
async def captura_status(request: Request) -> dict:
    return _status(request)


@router.put("")
async def captura_update(request: Request, body: CapturaUpdate) -> dict:
    config = _config(request)
    teclas = None
    if body.teclas is not None:
        try:
            teclas = normalizar(body.teclas)
        except CombinacaoInvalida as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        for nome, secao in (("do Nicx", "atalho"), ("do ditado", "ditado")):
            outra = getattr(config, secao, None)
            if outra is not None and teclas == _forma(outra.teclas):
                raise HTTPException(
                    status_code=400,
                    detail=f"{rotulo_de(teclas)} já é o atalho {nome}; escolha outra.",
                )

    def aplicar() -> None:
        with _lock:
            salvar_secao(
                config._config_path, "captura", {"ativo": body.ativo, "teclas": teclas}
            )
            if body.ativo is not None:
                config.captura.ativo = body.ativo
            if teclas is not None:
                config.captura.teclas = teclas
            try:
                from nicx.nucleo.config import load_config

                load_config.cache_clear()
            except Exception:  # noqa: BLE001
                pass
            gerenciador(request).aplicar(config.captura)

    try:
        await asyncio.to_thread(aplicar)
    except OSError as exc:
        logger.warning("Não foi possível salvar a captura rápida: %s", exc)
        raise HTTPException(
            status_code=500, detail="Não foi possível salvar no config.toml."
        ) from exc
    return _status(request)


__all__ = ["router"]
