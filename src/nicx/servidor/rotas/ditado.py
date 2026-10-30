"""Rotas do ditado universal (``/v1/ditado``).

- ``GET /v1/ditado``: configuração ``[ditado]`` e estado (``desligado``,
  ``pronto``, ``ouvindo``, ``transcrevendo``, ``em_uso``, ``erro``...).
- ``GET /v1/ditado/estado``: só o estado, para a janela flutuante acompanhar.
- ``PUT /v1/ditado``: grava ``ativo``/``teclas``/``modo``/``idioma``/``som`` no
  config.toml (sem apagar o resto) e reinicia o atalho na hora.

O texto ditado nunca passa por aqui.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nicx.atalho.servico import rotulo_de, salvar_secao
from nicx.atalho.teclas import CombinacaoInvalida
from nicx.ditado.servico import MODOS, ServicoDitado, validar_teclas
from nicx.nucleo.idiomas import IDIOMAS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ditado", tags=["ditado"])

_lock_gravacao = threading.Lock()


class DitadoUpdate(BaseModel):
    ativo: Optional[bool] = None
    teclas: Optional[str] = Field(default=None, max_length=64)
    modo: Optional[str] = Field(default=None, max_length=32)
    idioma: Optional[str] = Field(default=None, max_length=16)
    som: Optional[bool] = None


def _config(request: Request) -> Any:
    config = getattr(request.app.state, "config", None)
    if config is None:
        from nicx.nucleo.config import load_config

        config = load_config()
        request.app.state.config = config
    return config


def avisar_escuta(app: Any, ocupado: bool) -> None:
    """Deixa a escuta "Nicx, ligar" quieta enquanto o ditado ouve."""
    from nicx.servidor.rotas.escuta import WakeBusy

    estado = getattr(app.state, "wake_busy", None)
    if estado is None:
        estado = WakeBusy()
        app.state.wake_busy = estado
    estado.set("ditado", ocupado, ttl=10.0)


def criar_servico(app: Any) -> ServicoDitado:
    """O serviço do servidor: config do app, Whisper do app, aviso à escuta."""
    from nicx.ditado.servico import TranscritorLocal

    def obter_config() -> Any:
        config = getattr(app.state, "config", None)
        if config is None:
            from nicx.nucleo.config import load_config

            config = load_config()
            app.state.config = config
        return config

    return ServicoDitado(
        obter_config,
        transcrever=TranscritorLocal(
            obter_config, lambda: getattr(app.state, "speech_backend", None)
        ),
        avisar_ocupado=lambda ocupado: avisar_escuta(app, ocupado),
    )


def servico(request: Request) -> ServicoDitado:
    atual = getattr(request.app.state, "ditado", None)
    if atual is None:
        atual = criar_servico(request.app)
        request.app.state.ditado = atual
    return atual


def _status(request: Request) -> dict:
    ditado = _config(request).ditado
    return {
        "ativo": bool(ditado.ativo),
        "teclas": ditado.teclas,
        "rotulo": rotulo_de(ditado.teclas),
        "modo": ditado.modo,
        "idioma": ditado.idioma,
        "som": bool(ditado.som),
        "modos": list(MODOS),
        "idiomas": list(IDIOMAS),
        **servico(request).status(),
    }


@router.get("")
async def ditado_status(request: Request) -> dict:
    return _status(request)


@router.get("/estado")
async def ditado_estado(request: Request) -> dict:
    return {"estado": servico(request).estado}


@router.put("")
async def ditado_update(request: Request, body: DitadoUpdate) -> dict:
    config = _config(request)
    teclas = None
    if body.teclas is not None:
        try:
            teclas = validar_teclas(body.teclas, config.atalho.teclas).texto
        except CombinacaoInvalida as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.modo is not None and body.modo not in MODOS:
        raise HTTPException(
            status_code=400,
            detail="Modo desconhecido: use 'alternar' ou 'segurar'.",
        )
    idioma = None
    if body.idioma is not None:
        idioma = body.idioma.strip()
        if idioma and idioma not in IDIOMAS:
            raise HTTPException(
                status_code=400,
                detail="Idioma desconhecido: use " + ", ".join(IDIOMAS) + " ou vazio.",
            )

    def aplicar() -> None:
        with _lock_gravacao:
            salvar_secao(
                config._config_path,
                "ditado",
                {
                    "ativo": body.ativo,
                    "teclas": teclas,
                    "modo": body.modo,
                    "idioma": idioma,
                    "som": body.som,
                },
            )
            if body.ativo is not None:
                config.ditado.ativo = body.ativo
            if teclas is not None:
                config.ditado.teclas = teclas
            if body.modo is not None:
                config.ditado.modo = body.modo
            if idioma is not None:
                config.ditado.idioma = idioma
            if body.som is not None:
                config.ditado.som = body.som
            try:
                from nicx.nucleo.config import load_config

                load_config.cache_clear()
            except Exception:  # noqa: BLE001
                pass
            servico(request).aplicar()

    try:
        await asyncio.to_thread(aplicar)
    except OSError as exc:
        logger.warning("Não foi possível salvar o ditado: %s", exc)
        raise HTTPException(
            status_code=500, detail="Não foi possível salvar o ditado no config.toml."
        ) from exc
    return _status(request)


__all__ = ["avisar_escuta", "criar_servico", "router"]
