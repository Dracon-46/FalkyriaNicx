"""Rotas dos assistentes (leva F).

- ``GET /v1/assistentes?idioma=pt-BR``: os assistentes, o ativo, os modelos
  prontos, as ferramentas que o Nicx tem ligadas e os limites dos campos.
- ``POST /v1/assistentes``, ``PUT /v1/assistentes/{id}`` e
  ``DELETE /v1/assistentes/{id}``.
- ``PUT /v1/assistentes/ativo`` (``{"id": "..."}``; ``null`` volta para o Nicx).
- ``POST /v1/assistentes/propor`` (``{"descricao": "...", "idioma": "pt-BR"}``):
  o modelo local monta um rascunho; nada é salvo.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nicx.assistentes.modelo import (
    MAX_DESCRICAO,
    MAX_INSTRUCOES,
    MAX_NOME,
    MAX_SAUDACAO,
)

router = APIRouter(prefix="/v1/assistentes", tags=["assistentes"])
_NAO_ACHEI = "assistente não encontrado"


class AssistentePedido(BaseModel):
    nome: str = Field(min_length=1, max_length=MAX_NOME)
    instrucoes: str = Field(min_length=1, max_length=MAX_INSTRUCOES)
    descricao: str = Field(default="", max_length=MAX_DESCRICAO)
    ferramentas: list[str] = []
    memoria: bool = True
    saudacao: str = Field(default="", max_length=MAX_SAUDACAO)
    modelo: str = ""


class Ativo(BaseModel):
    id: Optional[str] = None


class Proposta(BaseModel):
    descricao: str = Field(min_length=3, max_length=500)
    idioma: Optional[str] = None


def _assistente(pedido: AssistentePedido):
    from nicx.assistentes.modelo import Assistente

    return Assistente.de_dict(pedido.model_dump())


def _ferramentas(request: Request) -> dict[str, str]:
    from nicx.assistentes.servico import ferramentas_do_agente

    return ferramentas_do_agente(getattr(request.app.state, "agent", None))


@router.get("")
async def listar(request: Request, idioma: Optional[str] = None):
    from nicx.assistentes import armazenamento, prontos

    ferramentas = _ferramentas(request)

    def _ler() -> dict[str, Any]:
        atual = armazenamento.ativo()
        return {
            "assistentes": [a.para_dict() for a in armazenamento.listar()],
            "ativo": atual.id if atual else None,
            "prontos": [a.para_dict() for a in prontos.prontos(idioma)],
            "ferramentas": [
                {"nome": nome, "descricao": desc} for nome, desc in ferramentas.items()
            ],
            "limites": {
                "nome": MAX_NOME,
                "descricao": MAX_DESCRICAO,
                "instrucoes": MAX_INSTRUCOES,
                "saudacao": MAX_SAUDACAO,
            },
        }

    return await asyncio.to_thread(_ler)


@router.post("")
async def criar(pedido: AssistentePedido):
    from nicx.assistentes import armazenamento
    from nicx.assistentes.modelo import AssistenteInvalido

    try:
        assistente = await asyncio.to_thread(armazenamento.criar, _assistente(pedido))
    except AssistenteInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return assistente.para_dict()


@router.put("/ativo")
async def ativar(pedido: Ativo):
    from nicx.assistentes import armazenamento

    try:
        await asyncio.to_thread(armazenamento.definir_ativo, pedido.id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="assistente não encontrado"
        ) from exc
    return {"ativo": pedido.id or None}


@router.post("/propor")
async def propor(request: Request, pedido: Proposta):
    from nicx.acoes.textos import codigo
    from nicx.assistentes.modelo import AssistenteInvalido
    from nicx.assistentes.servico import nome_livre
    from nicx.assistentes.servico import propor as _propor
    from nicx.servidor.rotas.nuvem import is_cloud_model

    engine = getattr(request.app.state, "engine", None)
    model = getattr(request.app.state, "model", None)
    if engine is None or not model:
        raise HTTPException(status_code=503, detail="sem modelo local")
    if getattr(engine, "is_cloud", False) or is_cloud_model(model):
        raise HTTPException(status_code=400, detail="assistentes só com modelos locais")

    def _montar():
        return nome_livre(
            _propor(
                pedido.descricao,
                codigo(pedido.idioma),
                engine,
                model,
                _ferramentas(request),
            )
        )

    try:
        assistente = await asyncio.to_thread(_montar)
    except AssistenteInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dados = assistente.para_dict()
    for chave in ("id", "criado_em", "atualizado_em"):
        dados.pop(chave, None)  # rascunho: ganha id ao ser salvo
    return dados


@router.put("/{assistente_id}")
async def atualizar(assistente_id: str, pedido: AssistentePedido):
    from nicx.assistentes import armazenamento
    from nicx.assistentes.modelo import AssistenteInvalido

    try:
        assistente = await asyncio.to_thread(
            armazenamento.atualizar, assistente_id, _assistente(pedido)
        )
    except AssistenteInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="assistente não encontrado"
        ) from exc
    return assistente.para_dict()


@router.delete("/{assistente_id}")
async def apagar(assistente_id: str):
    from nicx.assistentes import armazenamento

    if not await asyncio.to_thread(armazenamento.apagar, assistente_id):
        raise HTTPException(status_code=404, detail=_NAO_ACHEI)
    return {"ok": True}


__all__ = ["router"]
