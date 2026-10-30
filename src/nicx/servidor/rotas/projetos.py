"""Rotas dos projetos (``/v1/projetos``) para a página Projetos do app.

- ``GET /v1/projetos``: a lista (resumo de cada um) e o projeto da janela;
- ``POST /v1/projetos``: cria;
- ``GET/PATCH/DELETE /v1/projetos/{id}``: detalhe, muda (nome, objetivo,
  estado, próximos passos, pastas, arquivos, arquivado), apaga;
- ``POST /v1/projetos/{id}/decisoes``: anota uma decisão;
- ``POST /v1/projetos/{id}/pendencias``: nova pendência;
- ``PATCH/DELETE /v1/projetos/{id}/pendencias/{pid}``: feita/aberta, texto;
- ``GET /v1/projetos/{id}/sinais``: git e arquivos recentes das pastas.

Tudo fica no PC (``~/.nicx/projetos.json``); nada vai para logs.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nicx.projetos import deteccao
from nicx.projetos.armazenamento import (
    ProjetoErro,
    ProjetoJaExiste,
    ProjetoNaoEncontrado,
    Projetos,
)
from nicx.projetos.modelo import Projeto

router = APIRouter(prefix="/v1/projetos", tags=["projetos"])


class NovoProjeto(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    objetivo: str = Field(default="", max_length=2000)
    pastas: list[str] = Field(default_factory=list, max_length=30)


class MudancaProjeto(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=200)
    objetivo: Optional[str] = Field(default=None, max_length=2000)
    estado: Optional[str] = Field(default=None, max_length=2000)
    proximos_passos: Optional[list[str]] = Field(default=None, max_length=20)
    pastas: Optional[list[str]] = Field(default=None, max_length=30)
    arquivos: Optional[list[str]] = Field(default=None, max_length=30)
    arquivado: Optional[bool] = None


class Texto(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class MudancaPendencia(BaseModel):
    feita: Optional[bool] = None
    texto: Optional[str] = Field(default=None, max_length=2000)


def _resumo(projeto: Projeto) -> dict[str, Any]:
    return {
        "id": projeto.id,
        "nome": projeto.nome,
        "estado": projeto.estado,
        "objetivo": projeto.objetivo,
        "ultima_atividade": projeto.ultima_atividade,
        "pendencias_abertas": len(projeto.abertas),
        "arquivado": projeto.arquivado,
    }


def _erro(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjetoJaExiste):
        return HTTPException(409, detail=str(exc))
    if isinstance(exc, ProjetoNaoEncontrado):
        return HTTPException(404, detail=str(exc))
    return HTTPException(400, detail=str(exc))


def _obter(loja: Projetos, projeto_id: str) -> Projeto:
    projeto = loja.obter(projeto_id)
    if projeto is None:
        raise HTTPException(404, detail="Projeto não encontrado")
    return projeto


@router.get("")
async def listar(arquivados: bool = False) -> dict[str, Any]:
    loja = Projetos()

    def ler() -> dict[str, Any]:
        projetos = loja.listar(arquivados=arquivados)
        atual = deteccao.projeto_da_janela([p for p in projetos if not p.arquivado])
        return {
            "projetos": [_resumo(p) for p in projetos],
            "atual": atual.id if atual is not None else None,
        }

    return await asyncio.to_thread(ler)


@router.post("", status_code=201)
async def criar(corpo: NovoProjeto) -> dict[str, Any]:
    try:
        projeto = await asyncio.to_thread(
            Projetos().criar, corpo.nome, objetivo=corpo.objetivo, pastas=corpo.pastas
        )
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    return projeto.para_dict()


@router.get("/{projeto_id}")
async def detalhe(projeto_id: str) -> dict[str, Any]:
    return _obter(Projetos(), projeto_id).para_dict()


@router.patch("/{projeto_id}")
async def mudar(projeto_id: str, corpo: MudancaProjeto) -> dict[str, Any]:
    loja = Projetos()
    _obter(loja, projeto_id)
    campos = corpo.model_dump(exclude_none=True)

    def aplicar() -> Projeto:
        if "nome" in campos:
            loja.renomear(projeto_id, campos.pop("nome"))
        if "arquivado" in campos:
            loja.arquivar(projeto_id, campos.pop("arquivado"))
        if campos:
            loja.atualizar(projeto_id, **campos)
        return _obter(loja, projeto_id)

    try:
        projeto = await asyncio.to_thread(aplicar)
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    return projeto.para_dict()


@router.delete("/{projeto_id}")
async def apagar(projeto_id: str) -> dict[str, bool]:
    if not await asyncio.to_thread(Projetos().apagar, projeto_id):
        raise HTTPException(404, detail="Projeto não encontrado")
    return {"ok": True}


@router.post("/{projeto_id}/decisoes", status_code=201)
async def nova_decisao(projeto_id: str, corpo: Texto) -> dict[str, Any]:
    loja = Projetos()
    try:
        await asyncio.to_thread(loja.registrar_decisao, projeto_id, corpo.texto)
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    return _obter(loja, projeto_id).para_dict()


@router.post("/{projeto_id}/pendencias", status_code=201)
async def nova_pendencia(projeto_id: str, corpo: Texto) -> dict[str, Any]:
    loja = Projetos()
    try:
        await asyncio.to_thread(loja.adicionar_pendencia, projeto_id, corpo.texto)
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    return _obter(loja, projeto_id).para_dict()


@router.patch("/{projeto_id}/pendencias/{pendencia_id}")
async def mudar_pendencia(
    projeto_id: str, pendencia_id: str, corpo: MudancaPendencia
) -> dict[str, Any]:
    loja = Projetos()
    projeto = _obter(loja, projeto_id)
    if not any(p.id == pendencia_id for p in projeto.pendencias):
        raise HTTPException(404, detail="Pendência não encontrada")

    def aplicar() -> None:
        if corpo.texto is not None:
            loja.editar_pendencia(projeto_id, pendencia_id, corpo.texto)
        if corpo.feita is not None:
            loja.concluir_pendencia(projeto_id, pendencia_id, feita=corpo.feita)

    try:
        await asyncio.to_thread(aplicar)
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    return _obter(loja, projeto_id).para_dict()


@router.delete("/{projeto_id}/pendencias/{pendencia_id}")
async def apagar_pendencia(projeto_id: str, pendencia_id: str) -> dict[str, Any]:
    loja = Projetos()
    try:
        apagou = await asyncio.to_thread(
            loja.apagar_pendencia, projeto_id, pendencia_id
        )
    except ProjetoErro as exc:
        raise _erro(exc) from exc
    if not apagou:
        raise HTTPException(404, detail="Pendência não encontrada")
    return _obter(loja, projeto_id).para_dict()


@router.get("/{projeto_id}/sinais")
async def sinais(projeto_id: str) -> dict[str, Any]:
    """Git e arquivos recentes (só nomes e datas, nunca o conteúdo)."""
    projeto = _obter(Projetos(), projeto_id)

    def coletar() -> dict[str, Any]:
        git = None
        for pasta in projeto.pastas[:3]:
            info = deteccao.info_git(pasta)
            if info is not None:
                git = {
                    "pasta": info.pasta,
                    "branch": info.branch,
                    "commits": [
                        {"hash": c.hash, "data": c.data, "assunto": c.assunto}
                        for c in info.commits
                    ],
                    "alterados": list(info.alterados),
                    "total_alterados": info.total_alterados,
                }
                break
        recentes = [
            {"caminho": a.caminho, "modificado": a.modificado}
            for a in deteccao.arquivos_recentes(projeto.pastas[:3])
        ]
        return {"git": git, "recentes": recentes}

    return await asyncio.to_thread(coletar)


__all__ = ["router"]
