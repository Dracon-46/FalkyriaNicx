"""Ligar ao VS Code (Configurações → VS Code).

- ``GET /v1/vscode``: ``{"vscode": bool, "pacote": bool, "instalada": "0.1.0" | null}``.
- ``POST /v1/vscode/instalar``: instala (ou atualiza) a extensão "Nicx para VS Code".
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/vscode", tags=["vscode"])


@router.get("")
async def estado():
    from nicx.vscode import servico

    return await asyncio.to_thread(servico.estado)


@router.post("/instalar")
async def instalar():
    from nicx.vscode import servico

    try:
        return await asyncio.to_thread(servico.instalar)
    except servico.VSCodeErro as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


__all__ = ["router"]
