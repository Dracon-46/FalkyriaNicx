"""Pesquisar em tudo (página Pesquisar do app).

``GET /v1/busca?q=...&fontes=projeto,nota`` (fontes opcional): projetos,
notas, lembretes, agenda, memória, histórico e tarefas do modo Trabalho.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1/busca", tags=["busca"])


@router.get("")
async def buscar(
    q: str = Query("", max_length=200),
    fontes: str = Query("", max_length=200),
):
    from nicx.busca import servico

    escolhidas = [f.strip() for f in fontes.split(",") if f.strip()] or None
    return await asyncio.to_thread(servico.buscar, q, escolhidas)


__all__ = ["router"]
