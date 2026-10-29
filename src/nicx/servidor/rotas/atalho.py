"""Rotas do atalho global de teclado (``/v1/atalho``).

- ``GET /v1/atalho``: configuração ``[atalho]`` e estado do registro
  (``registrado``, ``em_uso`` por outro programa, ``desligado``...).
- ``PUT /v1/atalho``: grava ``ativo``/``teclas``/``acao`` no config.toml (sem
  apagar o resto) e reinicia o atalho na hora.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nicx.atalho.acao import ACOES
from nicx.atalho.servico import GerenciadorAtalho, rotulo_de, salvar_config
from nicx.atalho.teclas import CombinacaoInvalida, normalizar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/atalho", tags=["atalho"])

_lock_gravacao = threading.Lock()


class AtalhoUpdate(BaseModel):
    ativo: Optional[bool] = None
    teclas: Optional[str] = Field(default=None, max_length=64)
    acao: Optional[str] = Field(default=None, max_length=32)


def _config(request: Request) -> Any:
    config = getattr(request.app.state, "config", None)
    if config is None:
        from nicx.nucleo.config import load_config

        config = load_config()
        request.app.state.config = config
    return config


def gerenciador(request: Request) -> GerenciadorAtalho:
    atual = getattr(request.app.state, "atalho", None)
    if atual is None:
        atual = GerenciadorAtalho()
        request.app.state.atalho = atual
    return atual


def _status(request: Request) -> dict:
    atalho = _config(request).atalho
    return {
        "ativo": bool(atalho.ativo),
        "teclas": atalho.teclas,
        "rotulo": rotulo_de(atalho.teclas),
        "acao": atalho.acao,
        **gerenciador(request).status(),
    }


@router.get("")
async def atalho_status(request: Request) -> dict:
    return _status(request)


@router.put("")
async def atalho_update(request: Request, body: AtalhoUpdate) -> dict:
    teclas = None
    if body.teclas is not None:
        try:
            teclas = normalizar(body.teclas)
        except CombinacaoInvalida as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.acao is not None and body.acao not in ACOES:
        raise HTTPException(
            status_code=400,
            detail="Ação desconhecida: use 'flutuante' (mascote) ou 'app'.",
        )

    config = _config(request)

    def aplicar() -> None:
        with _lock_gravacao:
            salvar_config(
                config._config_path, ativo=body.ativo, teclas=teclas, acao=body.acao
            )
            if body.ativo is not None:
                config.atalho.ativo = body.ativo
            if teclas is not None:
                config.atalho.teclas = teclas
            if body.acao is not None:
                config.atalho.acao = body.acao
            try:
                from nicx.nucleo.config import load_config

                load_config.cache_clear()
            except Exception:  # noqa: BLE001
                pass
            gerenciador(request).aplicar(config.atalho)

    try:
        await asyncio.to_thread(aplicar)
    except OSError as exc:
        logger.warning("Não foi possível salvar o atalho de teclado: %s", exc)
        raise HTTPException(
            status_code=500, detail="Não foi possível salvar o atalho no config.toml."
        ) from exc
    return _status(request)


__all__ = ["router"]
