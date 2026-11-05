"""Atualizações do Nicx (página Atualizações do app).

- ``GET /v1/atualizacao``: versão instalada, a mais nova conhecida,
  novidades, progresso do download e se esta instalação se atualiza pelo app.
- ``POST /v1/atualizacao/verificar``: procura agora.
- ``POST /v1/atualizacao/baixar``: baixa o instalador (em segundo plano;
  acompanhe pelo ``GET``).
- ``POST /v1/atualizacao/instalar``: abre o instalador por cima; o servidor
  é encerrado pelo instalador e volta sozinho na versão nova.
- ``PUT /v1/atualizacao/config`` (``{"automatica": bool}``): procurar sozinho
  uma vez por dia (grava em ``[atualizacao]`` no config.toml).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StrictBool

router = APIRouter(prefix="/v1/atualizacao", tags=["atualizacao"])


def _cfg(request: Request):
    config = getattr(request.app.state, "config", None)
    cfg = getattr(config, "atualizacao", None)
    if cfg is None:
        from nicx.atualizacao.servico import _config

        cfg = _config()
    return cfg


class AtualizacaoUpdate(BaseModel):
    automatica: StrictBool


@router.get("")
async def estado(request: Request):
    from nicx.atualizacao import servico

    return await asyncio.to_thread(servico.estado, _cfg(request))


@router.post("/verificar")
async def verificar(request: Request):
    from nicx.atualizacao import servico

    return await asyncio.to_thread(servico.verificar, _cfg(request))


@router.post("/baixar")
async def baixar():
    from nicx.atualizacao import servico

    try:
        return await asyncio.to_thread(servico.baixar)
    except servico.AtualizacaoErro as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/instalar")
async def instalar():
    from nicx.atualizacao import servico

    try:
        return await asyncio.to_thread(servico.instalar)
    except servico.AtualizacaoErro as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/config")
async def configurar(request: Request, corpo: AtualizacaoUpdate):
    from nicx.atalho.servico import salvar_secao
    from nicx.atualizacao import servico
    from nicx.nucleo.paths import get_config_path

    config = getattr(request.app.state, "config", None)
    caminho = getattr(config, "_config_path", None) or get_config_path()
    await asyncio.to_thread(
        salvar_secao, caminho, "atualizacao", {"automatica": corpo.automatica}
    )
    cfg = _cfg(request)
    cfg.automatica = corpo.automatica
    try:
        from nicx.nucleo.config import load_config

        load_config().atualizacao.automatica = corpo.automatica
    except Exception:  # noqa: BLE001 - o arquivo já está gravado
        pass
    return await asyncio.to_thread(servico.estado, cfg)


__all__ = ["router"]
