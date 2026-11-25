"""Exportar todos os meus dados (Configurações → Dados).

``POST /v1/meus-dados/exportar`` (``{"conversas": ...}`` opcional, as conversas
que o app guarda) devolve um ``.zip`` com tudo o que o Nicx guarda neste PC,
sem segredos. Ver :mod:`nicx.privacidade.exportar`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

router = APIRouter(prefix="/v1/meus-dados", tags=["meus-dados"])

MAX_CORPO = 200 * 1024 * 1024


@router.post("/exportar")
async def exportar(request: Request) -> Response:
    from nicx.privacidade import exportar as exp

    corpo = await request.body()
    if len(corpo) > MAX_CORPO:
        raise HTTPException(status_code=413, detail="conversas grandes demais")
    conversas = None
    if corpo.strip():
        try:
            conversas = json.loads(corpo).get("conversas")
        except (ValueError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="JSON inválido") from exc
    dados, resumo = await asyncio.to_thread(exp.montar, conversas)
    nome = f"nicx-meus-dados-{date.today().isoformat()}.zip"
    return Response(
        content=dados,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "X-Nicx-Arquivos": str(resumo["arquivos"]),
        },
    )


__all__ = ["router"]
