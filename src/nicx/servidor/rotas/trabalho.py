"""Modo Trabalho (página Trabalho do app).

- ``POST /v1/trabalho/escolher-pasta``: abre a janela do Windows para escolher
  a pasta (neste PC) e devolve o caminho.
- ``POST /v1/trabalho`` (``{"pasta", "pedido"}``): cria a tarefa e monta o plano.
- ``GET /v1/trabalho`` e ``GET /v1/trabalho/{id}``: tarefas e andamento.
- ``POST /v1/trabalho/{id}/aprovar`` (``{"passos": [...]}`` opcional): executa.
- ``POST .../pausar``, ``.../continuar``, ``.../parar``.
- ``POST .../responder`` (``{"confirmado": bool}``): resposta a um "posso apagar?".
- ``POST .../desfazer``: volta a pasta para como estava.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool

router = APIRouter(prefix="/v1/trabalho", tags=["trabalho"])

_ESCOLHER = (
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
    "print(filedialog.askdirectory(title='Pasta para o Nicx trabalhar', "
    "mustexist=True) or '')\n"
)


class Novo(BaseModel):
    pasta: str = Field(min_length=1, max_length=1000)
    pedido: str = Field(min_length=1, max_length=4000)


class Aprovacao(BaseModel):
    passos: Optional[list[str]] = Field(default=None, max_length=20)


class Resposta(BaseModel):
    confirmado: StrictBool


def _motor(request: Request):
    return getattr(request.app.state, "engine", None), getattr(
        request.app.state, "model", ""
    )


async def _rodar(funcao, *args):
    from nicx.trabalho.pasta import ForaDaPasta
    from nicx.trabalho.servico import TrabalhoErro

    try:
        return await asyncio.to_thread(funcao, *args)
    except (TrabalhoErro, ForaDaPasta) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/escolher-pasta")
async def escolher_pasta():
    """Janela de pasta do sistema, em processo separado (o Tk não vive no servidor)."""

    def escolher() -> str:
        r = subprocess.run(
            [sys.executable, "-c", _ESCOLHER],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        return (r.stdout or "").strip()

    try:
        caminho = await asyncio.to_thread(escolher)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(
            status_code=409, detail="não consegui abrir a janela de pastas"
        ) from exc
    return {"pasta": caminho.replace("/", "\\") if sys.platform == "win32" else caminho}


@router.get("")
async def listar():
    from nicx.trabalho import servico

    return {"tarefas": await asyncio.to_thread(servico.listar)}


@router.post("")
async def criar(request: Request, corpo: Novo):
    from nicx.trabalho import servico

    engine, modelo = _motor(request)
    return await _rodar(servico.criar, corpo.pasta, corpo.pedido, engine, modelo)


@router.get("/{tarefa_id}")
async def ver(tarefa_id: str):
    from nicx.trabalho import servico

    return await _rodar(servico.ver, tarefa_id)


@router.post("/{tarefa_id}/aprovar")
async def aprovar(request: Request, tarefa_id: str, corpo: Aprovacao):
    from nicx.trabalho import servico

    engine, modelo = _motor(request)
    return await _rodar(servico.aprovar, tarefa_id, corpo.passos, engine, modelo)


@router.post("/{tarefa_id}/pausar")
async def pausar(tarefa_id: str):
    from nicx.trabalho import servico

    return await _rodar(servico.pausar, tarefa_id)


@router.post("/{tarefa_id}/continuar")
async def continuar(tarefa_id: str):
    from nicx.trabalho import servico

    return await _rodar(servico.continuar, tarefa_id)


@router.post("/{tarefa_id}/parar")
async def parar(tarefa_id: str):
    from nicx.trabalho import servico

    return await _rodar(servico.parar, tarefa_id)


@router.post("/{tarefa_id}/responder")
async def responder(tarefa_id: str, corpo: Resposta):
    from nicx.trabalho import servico

    return await _rodar(servico.responder, tarefa_id, corpo.confirmado)


@router.post("/{tarefa_id}/desfazer")
async def desfazer(tarefa_id: str):
    from nicx.trabalho import servico

    return await _rodar(servico.desfazer, tarefa_id)


__all__ = ["router"]
