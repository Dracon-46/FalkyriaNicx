"""Rotas do planejador de objetivos (leva D).

- ``POST /v1/planejador/propor`` (``{"objetivo", "prazo": "AAAA-MM-DD", "idioma"}``):
  o modelo local propõe as etapas; nada é salvo.
- ``POST /v1/planejador`` (``{"objetivo", "prazo", "etapas": [...], "nome", "idioma"}``):
  cria o projeto do plano com datas e lembretes.
- ``GET /v1/planejador/{projeto_id}``: progresso.
- ``POST /v1/planejador/{projeto_id}/reajustar`` (``{"prazo": "AAAA-MM-DD"}`` opcional).
- ``POST /v1/planejador/prazo`` (``{"texto": "até dezembro"}``): a data do texto.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/planejador", tags=["planejador"])


class Proposta(BaseModel):
    objetivo: str = Field(min_length=3, max_length=300)
    prazo: date
    idioma: Optional[str] = None


class Plano(BaseModel):
    objetivo: str = Field(min_length=3, max_length=300)
    prazo: date
    etapas: list[dict[str, Any]]
    nome: str = ""
    idioma: str = ""


class Reajuste(BaseModel):
    prazo: Optional[date] = None


class TextoPrazo(BaseModel):
    texto: str = Field(min_length=1, max_length=100)


def _modelo_local(request: Request) -> tuple[Any, str]:
    engine = getattr(request.app.state, "engine", None)
    model = getattr(request.app.state, "model", None)
    if engine is None or not model:
        raise HTTPException(status_code=503, detail="sem modelo local")
    from nicx.servidor.rotas.nuvem import is_cloud_model

    if getattr(engine, "is_cloud", False) or is_cloud_model(model):
        raise HTTPException(status_code=400, detail="planos só com modelos locais")
    return engine, model


@router.post("/propor")
async def propor(request: Request, pedido: Proposta):
    from nicx.acoes.textos import codigo
    from nicx.planejador.servico import PlanoErro
    from nicx.planejador.servico import propor as _propor

    engine, model = _modelo_local(request)
    try:
        etapas = await asyncio.to_thread(
            _propor, pedido.objetivo, pedido.prazo, codigo(pedido.idioma), engine, model
        )
    except PlanoErro as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "etapas": [e.para_dict() for e in etapas],
        "prazo": pedido.prazo.isoformat(),
    }


@router.post("")
async def criar(pedido: Plano):
    from nicx.planejador.servico import Etapa, PlanoErro, criar_plano, progresso
    from nicx.projetos.armazenamento import ProjetoErro

    etapas = [
        e for e in (Etapa.de_dict(d, i) for i, d in enumerate(pedido.etapas)) if e
    ]
    try:
        projeto = await asyncio.to_thread(
            criar_plano,
            pedido.objetivo,
            pedido.prazo,
            etapas,
            nome=pedido.nome,
            idioma=pedido.idioma,
        )
    except (PlanoErro, ProjetoErro) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"projeto": projeto.para_dict(), "progresso": progresso(projeto)}


@router.post("/prazo")
async def prazo(pedido: TextoPrazo):
    from nicx.planejador.pedidos import _normalizar
    from nicx.planejador.prazo import interpretar

    data = interpretar(_normalizar(pedido.texto))
    return {"prazo": data.isoformat() if data else None}


@router.get("/{projeto_id}")
async def ver(projeto_id: str):
    from nicx.planejador.servico import progresso
    from nicx.projetos.armazenamento import Projetos

    projeto = await asyncio.to_thread(Projetos().obter, projeto_id)
    if projeto is None:
        raise HTTPException(status_code=404, detail="plano não encontrado")
    return progresso(projeto)


@router.post("/{projeto_id}/reajustar")
async def reajustar(projeto_id: str, pedido: Reajuste):
    from nicx.planejador.servico import PlanoErro, progresso
    from nicx.planejador.servico import reajustar as _reajustar

    try:
        projeto = await asyncio.to_thread(_reajustar, projeto_id, pedido.prazo)
    except PlanoErro as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return progresso(projeto)


__all__ = ["router"]
