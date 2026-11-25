"""Caixa de entrada de decisões (sininho no topo do app).

- ``GET /v1/caixa``: decisões pendentes, avisos e a atividade em segundo plano.
- ``POST /v1/caixa/dispensar`` (``{"ids": [...]}`` ou ``{"todos": true}``):
  esconde avisos. Decisões somem quando a pessoa decide.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/caixa", tags=["caixa"])


class Dispensa(BaseModel):
    ids: Optional[list[str]] = Field(default=None, max_length=200)
    todos: bool = False


def _fontes(request: Request) -> dict:
    from nicx.servidor.rotas.aprovacoes import _get_store

    try:
        aprovacoes = _get_store()
    except Exception:  # noqa: BLE001
        aprovacoes = None
    return {
        "aprovacoes": aprovacoes,
        "agentes": getattr(request.app.state, "agent_manager", None),
    }


@router.get("")
async def ver(request: Request):
    from nicx.caixa import servico

    return await asyncio.to_thread(lambda: servico.montar(**_fontes(request)))


@router.post("/dispensar")
async def dispensar(request: Request, corpo: Dispensa):
    from nicx.caixa import servico

    if corpo.todos:
        n = await asyncio.to_thread(
            lambda: servico.dispensar_avisos(**_fontes(request))
        )
    else:
        n = await asyncio.to_thread(servico.dispensar, corpo.ids or [])
    return {"dispensados": n}


__all__ = ["router"]
