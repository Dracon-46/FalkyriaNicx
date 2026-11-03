"""Rotas das rotinas (leva D).

- ``GET /v1/rotinas``: as rotinas e os modelos prontos (modo foco).
- ``POST /v1/rotinas`` / ``PUT /v1/rotinas/{id}`` / ``DELETE /v1/rotinas/{id}``.
- ``POST /v1/rotinas/{id}/executar`` (``{"idioma": "pt-BR"}``): roda agora.
- ``POST /v1/rotinas/interpretar`` (``{"texto": "...", "idioma": "pt-BR"}``): os
  passos que a frase descreve, sem salvar (para a tela montar a rotina).
- ``GET /v1/rotinas/opcoes``: tipos de passo, apps, pastas e apps que dá para fechar.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/rotinas", tags=["rotinas"])


class RotinaPedido(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    passos: list[dict[str, Any]]
    frases: list[str] = []
    agenda: Optional[dict[str, Any]] = None
    ativa: bool = True
    idioma: str = ""


class Idioma(BaseModel):
    idioma: Optional[str] = None


class Texto(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)
    idioma: Optional[str] = None


def _rotina(pedido: RotinaPedido):
    from nicx.rotinas.modelo import Rotina

    return Rotina.de_dict(pedido.model_dump())


def _dados(rotina) -> dict[str, Any]:
    return rotina.para_dict()


@router.get("")
async def listar(idioma: Optional[str] = None):
    from nicx.rotinas import armazenamento, servico

    def _ler():
        return {
            "rotinas": [_dados(r) for r in armazenamento.listar()],
            "modelos": [_dados(r) for r in servico.modelos(idioma)],
        }

    return await asyncio.to_thread(_ler)


def _sem_apelidos(apps) -> list[dict[str, str]]:
    """Um item por app (o catálogo tem vários apelidos para o mesmo)."""
    vistos, itens = set(), []
    for chave, app in apps.items():
        if id(app) not in vistos:
            vistos.add(id(app))
            itens.append({"chave": chave, "rotulo": app.label})
    return itens


@router.get("/opcoes")
async def opcoes():
    from nicx.acoes.intencoes import APPS
    from nicx.acoes.rotinas import CLOSABLE, FOLDERS
    from nicx.rotinas.modelo import PASSOS_PERMITIDOS

    return {
        "tipos": sorted(PASSOS_PERMITIDOS),
        "apps": _sem_apelidos(APPS),
        "fechar": [{"chave": k, "rotulo": v[0]} for k, v in CLOSABLE.items()],
        "pastas": sorted(set(FOLDERS)),
    }


@router.post("")
async def criar(pedido: RotinaPedido):
    from nicx.rotinas import armazenamento
    from nicx.rotinas.modelo import RotinaInvalida

    try:
        rotina = await asyncio.to_thread(armazenamento.criar, _rotina(pedido))
    except RotinaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _dados(rotina)


@router.put("/{rotina_id}")
async def atualizar(rotina_id: str, pedido: RotinaPedido):
    from nicx.rotinas import armazenamento
    from nicx.rotinas.modelo import RotinaInvalida

    try:
        rotina = await asyncio.to_thread(
            armazenamento.atualizar, rotina_id, _rotina(pedido)
        )
    except RotinaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rotina não encontrada") from exc
    return _dados(rotina)


@router.delete("/{rotina_id}")
async def apagar(rotina_id: str):
    from nicx.rotinas import armazenamento

    if not await asyncio.to_thread(armazenamento.apagar, rotina_id):
        raise HTTPException(status_code=404, detail="rotina não encontrada")
    return {"ok": True}


@router.post("/interpretar")
async def interpretar(pedido: Texto):
    from nicx.rotinas.servico import interpretar_passos

    lido = await asyncio.to_thread(interpretar_passos, pedido.texto, pedido.idioma)
    return {
        "passos": [asdict(p) for p in lido["passos"]],
        "agenda": asdict(lido["agenda"]) if lido["agenda"] else None,
        "nao_entendi": lido["nao_entendi"],
        "proibidos": lido["proibidos"],
    }


@router.post("/{rotina_id}/executar")
async def executar(rotina_id: str, pedido: Idioma):
    from nicx.rotinas import armazenamento, servico

    rotina = armazenamento.obter(rotina_id)
    if rotina is None and rotina_id == "modelo-foco":
        rotina = servico.foco(pedido.idioma)
    if rotina is None:
        raise HTTPException(status_code=404, detail="rotina não encontrada")
    ok, mensagem = await asyncio.to_thread(
        servico.executar, rotina, "app", pedido.idioma
    )
    return {"ok": ok, "mensagem": mensagem}


__all__ = ["router"]
