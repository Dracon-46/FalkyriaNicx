"""Diagnóstico (Configurações → Diagnóstico): ``GET /v1/diagnostico``.

Verificações rápidas que não mudam nada: Ollama e modelo, componentes,
memória e disco, pasta do Nicx, microfone (só lista), voz, atalhos e
integridade do histórico. Ver :mod:`nicx.diagnostico.verificacoes`.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1/diagnostico", tags=["diagnostico"])


@router.get("")
async def diagnostico(request: Request) -> dict:
    from nicx.diagnostico import verificacoes

    config = getattr(request.app.state, "config", None)
    return await asyncio.to_thread(verificacoes.rodar, config, request.app.state)


__all__ = ["router"]
