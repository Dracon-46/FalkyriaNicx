"""Rotas do resumo do dia (``/v1/resumo``).

- ``GET /v1/resumo?dia=AAAA-MM-DD&idioma=pt-BR&refinar=false``: o resumo
  (texto pronto, sem modelo) e as seções. ``refinar=true`` pede ao modelo
  local para deixar o texto mais natural; se ele falhar (ou o modelo for da
  nuvem), volta o texto sem modelo.
- ``GET /v1/resumo/config``: ``[resumo]`` atual e a data do último envio.
- ``PUT /v1/resumo/config``: liga/desliga, hora, dias, falar e notificar
  (grava no config.toml e já vale para o servidor).

O conteúdo do resumo não vai para analytics nem para os logs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/resumo", tags=["resumo"])


class ResumoUpdate(BaseModel):
    ativo: Optional[bool] = None
    hora: Optional[str] = None
    falar: Optional[bool] = None
    notificar: Optional[bool] = None
    dias: Optional[List[str]] = None

    @field_validator("hora")
    @classmethod
    def _hora(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        from nicx.resumo.agendador import hora_de

        hora = hora_de(valor)
        if hora is None:
            raise ValueError("hora deve ser HH:MM")
        return f"{hora:%H:%M}"

    @field_validator("dias")
    @classmethod
    def _dias(cls, valor: Optional[List[str]]) -> Optional[List[str]]:
        if valor is None:
            return None
        from nicx.resumo.agendador import DIAS, normalizar_dias

        desconhecidos = [d for d in valor if str(d).strip().lower() not in DIAS]
        if desconhecidos:
            raise ValueError(f"dias desconhecidos: {desconhecidos}")
        return normalizar_dias(valor)


def _cfg(request: Request) -> Any:
    config = getattr(request.app.state, "config", None)
    cfg = getattr(config, "resumo", None)
    if cfg is None:
        from nicx.resumo.agendador import config as config_atual

        cfg = config_atual()
    return cfg


def _status(cfg: Any) -> dict:
    from nicx.resumo.agendador import DIAS, normalizar_dias, ultimo_envio

    ultimo = ultimo_envio()
    return {
        "ativo": bool(cfg.ativo),
        "hora": str(cfg.hora),
        "falar": bool(cfg.falar),
        "notificar": bool(cfg.notificar),
        "dias": normalizar_dias(cfg.dias),
        "opcoes_dias": list(DIAS),
        "ultimo_envio": ultimo.isoformat() if ultimo else None,
    }


def _config_path(request: Request):
    config = getattr(request.app.state, "config", None)
    path = getattr(config, "_config_path", None)
    if path is None:
        import os
        from pathlib import Path

        from nicx.nucleo.paths import get_config_path

        custom = os.environ.get("NICX_CONFIG")
        path = Path(custom).expanduser() if custom else get_config_path()
    return path


def salvar(path, valores: dict) -> None:
    """Grava ``[resumo]`` no config.toml, preservando o resto."""
    import tomlkit

    if path.exists():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = tomlkit.document()
    if "resumo" not in doc:
        doc.add("resumo", tomlkit.table())
    for chave, valor in valores.items():
        doc["resumo"][chave] = valor
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _atualizar_config_em_cache(valores: dict) -> None:
    """O agendador lê ``load_config()``: vale lá também."""
    try:
        from nicx.nucleo.config import load_config

        cache = load_config().resumo
        for chave, valor in valores.items():
            setattr(cache, chave, valor)
    except Exception:  # noqa: BLE001 - o arquivo já está gravado
        logger.debug("Config em memória não atualizada", exc_info=True)


@router.get("")
async def resumo_do_dia(
    request: Request,
    dia: Optional[str] = Query(default=None),
    idioma: Optional[str] = Query(default=None),
    refinar: bool = Query(default=False),
):
    from nicx.resumo import montar
    from nicx.resumo import refinar as refinar_texto

    alvo: Optional[date] = None
    if dia:
        try:
            alvo = date.fromisoformat(dia)
        except ValueError:
            raise HTTPException(status_code=422, detail="dia deve ser AAAA-MM-DD")
    resumo = await asyncio.to_thread(montar, alvo, idioma)
    dados = resumo.como_dict()
    dados["refinado"] = False
    if refinar:
        engine = getattr(request.app.state, "engine", None)
        model = getattr(request.app.state, "model", None)
        nuvem = bool(getattr(engine, "is_cloud", False))
        if model and not nuvem:
            from nicx.servidor.rotas.nuvem import is_cloud_model

            nuvem = is_cloud_model(model)
        if engine is not None and model and not nuvem:
            try:
                dados["texto"] = await asyncio.to_thread(
                    refinar_texto, resumo.texto, resumo.idioma, engine, model
                )
                dados["refinado"] = True
            except Exception as exc:  # noqa: BLE001 - fica o texto sem modelo
                logger.info("Resumo não refinado: %s", type(exc).__name__)
    return dados


@router.get("/config")
async def resumo_config(request: Request):
    return await asyncio.to_thread(_status, _cfg(request))


@router.put("/config")
async def resumo_update(request: Request, body: ResumoUpdate):
    valores = body.model_dump(exclude_none=True)
    cfg = _cfg(request)
    if valores:
        await asyncio.to_thread(salvar, _config_path(request), valores)
        for chave, valor in valores.items():
            setattr(cfg, chave, valor)
        _atualizar_config_em_cache(valores)
    return await asyncio.to_thread(_status, cfg)


__all__ = ["router", "salvar"]
