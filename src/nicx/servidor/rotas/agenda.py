"""Rotas da agenda (``/v1/agenda``).

- ``GET /v1/agenda/config``: calendário padrão de "manda pro calendário" e
  quais contas (Google, Outlook) estão conectadas e podem criar eventos.
- ``PUT /v1/agenda/config``: troca o calendário padrão (grava em
  ``[agenda] calendario_padrao`` no config.toml).
"""

from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/v1/agenda", tags=["agenda"])


class AgendaUpdate(BaseModel):
    calendario_padrao: Literal["windows", "google", "outlook", "outlook_trabalho"]


def _status() -> dict:
    from nicx.acoes import calendarios

    return {
        "calendario_padrao": calendarios.calendario_padrao(),
        "opcoes": list(calendarios.DESTINOS),
        **calendarios.estado_contas(),
    }


@router.get("/config")
async def agenda_config():
    return await asyncio.to_thread(_status)


@router.put("/config")
async def agenda_update(request: Request, body: AgendaUpdate):
    from nicx.acoes import calendarios

    await asyncio.to_thread(calendarios.salvar_padrao, body.calendario_padrao)
    # O servidor pode ter a própria cópia da config: vale nela também.
    config = getattr(request.app.state, "config", None)
    agenda_cfg = getattr(config, "agenda", None)
    if agenda_cfg is not None:
        agenda_cfg.calendario_padrao = body.calendario_padrao
    return await asyncio.to_thread(_status)


__all__ = ["router"]
