"""Rotas do histórico universal, do desfazer e da autonomia (leva C).

- ``GET /v1/historico?busca=&tipos=nota,lembrete&desde=AAAA-MM-DD``
  ``&ate=AAAA-MM-DD&limite=50&antes_de=ID``:
  atividades da mais recente para a mais antiga (``mais`` diz se há outras).
- ``POST /v1/historico/desfazer`` com ``{"id": 12}`` (ou sem id: a última que dá).
- ``GET /v1/historico/integridade``: confere a cadeia de hashes do registro.
- ``GET /v1/autonomia`` e ``PUT /v1/autonomia`` com ``{"nivel": "assistido"}``.

Tudo fica no PC: nada daqui vai para analytics nem para os logs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["historico"])


class DesfazerPedido(BaseModel):
    id: Optional[int] = None
    idioma: Optional[str] = None


class AutonomiaPedido(BaseModel):
    nivel: str


def _data(texto: Optional[str], fim: bool = False) -> Optional[datetime]:
    if not texto:
        return None
    try:
        dia = date.fromisoformat(texto)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="data inválida (use AAAA-MM-DD)"
        ) from exc
    return datetime.combine(dia, time.max if fim else time.min)


@router.get("/v1/historico")
async def listar(
    busca: str = "",
    tipos: str = "",
    desde: Optional[str] = None,
    ate: Optional[str] = None,
    so_desfaziveis: bool = False,
    limite: int = Query(50, ge=1, le=500),
    antes_de: Optional[int] = None,
):
    from nicx.historico.registro import TIPOS, registro

    escolhidos = [t for t in (p.strip() for p in tipos.split(",")) if t]
    invalidos = [t for t in escolhidos if t not in TIPOS]
    if invalidos:
        raise HTTPException(
            status_code=400, detail=f"tipos inválidos: {', '.join(invalidos)}"
        )

    def _ler():
        itens = registro().listar(
            busca=busca,
            tipos=escolhidos or None,
            desde=_data(desde),
            ate=_data(ate, fim=True),
            so_desfaziveis=so_desfaziveis,
            limite=limite + 1,
            antes_de=antes_de,
        )
        return {
            "itens": [a.para_dict() for a in itens[:limite]],
            "mais": len(itens) > limite,
        }

    return await asyncio.to_thread(_ler)


@router.post("/v1/historico/desfazer")
async def desfazer(pedido: DesfazerPedido):
    from nicx.historico.desfazer import desfazer as _desfazer
    from nicx.historico.registro import origem

    def _rodar():
        with origem("app"):
            return _desfazer(pedido.id, idioma=pedido.idioma)

    ok, mensagem = await asyncio.to_thread(_rodar)
    return {"ok": ok, "mensagem": mensagem}


@router.get("/v1/historico/integridade")
async def integridade():
    from nicx.historico.registro import registro

    return await asyncio.to_thread(lambda: registro().verificar())


def _config_path(request: Request):
    from nicx.servidor.rotas.resumo import _config_path as caminho

    return caminho(request)


def _estado() -> dict:
    from nicx.historico import autonomia

    return {
        "nivel": autonomia.nivel_atual(),
        "niveis": autonomia.descricao_niveis(),
        "riscos": list(autonomia.RISCOS),
    }


@router.get("/v1/autonomia")
async def ver_autonomia():
    return _estado()


@router.put("/v1/autonomia")
async def mudar_autonomia(request: Request, pedido: AutonomiaPedido):
    from nicx.historico import autonomia
    from nicx.historico.registro import anotar

    nivel = pedido.nivel.strip().lower().replace("ô", "o")
    if nivel not in autonomia.NIVEIS:
        raise HTTPException(
            status_code=400, detail=f"nível inválido: use {', '.join(autonomia.NIVEIS)}"
        )
    anterior = autonomia.nivel_atual()

    def _gravar() -> None:
        import tomlkit

        path = _config_path(request)
        if path.exists():
            doc = tomlkit.parse(path.read_text(encoding="utf-8"))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = tomlkit.document()
        if "autonomia" not in doc:
            doc.add("autonomia", tomlkit.table())
        doc["autonomia"]["nivel"] = nivel
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    await asyncio.to_thread(_gravar)
    for cfg in (getattr(request.app.state, "config", None), _cache()):
        if cfg is not None and hasattr(cfg, "autonomia"):
            cfg.autonomia.nivel = nivel
    if anterior != nivel:
        anotar(
            "acao",
            f"autonomia: {anterior} -> {nivel}",
            detalhe={"acao": "autonomia", "de": anterior, "para": nivel},
            origem="app",
        )
    return _estado()


def _cache():
    try:
        from nicx.nucleo.config import load_config

        return load_config()
    except Exception:  # noqa: BLE001
        return None


__all__ = ["router"]
