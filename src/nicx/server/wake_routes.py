"""Rotas do "Nicx, ligar" (``/v1/speech/wake``).

- ``GET  /v1/speech/wake``: está ativada? rodando? inicia com o Windows?
- ``PUT  /v1/speech/wake``: liga/desliga a escuta e o início automático.
- ``POST /v1/speech/wake/busy``: a interface avisa que está em conversa por voz
  ou falando (com validade curta, renovada enquanto durar).
- ``GET  /v1/speech/wake/busy``: a escuta pergunta antes de transcrever, para
  nunca se ativar com a própria voz do Nicx.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/speech/wake", tags=["speech"])

# Uma aba que fechou sem avisar não deixa a escuta muda para sempre.
_MAX_TTL_S = 30.0


class WakeBusy:
    """Fontes ocupadas (aba, janela do mascote) com prazo de validade."""

    def __init__(self, clock=time.monotonic) -> None:  # noqa: ANN001
        self._clock = clock
        self._until: dict[str, float] = {}

    def set(self, source: str, busy: bool, ttl: float = 10.0) -> None:
        if busy:
            ttl = max(0.5, min(float(ttl), _MAX_TTL_S))
            self._until[source] = self._clock() + ttl
        else:
            self._until.pop(source, None)

    def busy(self) -> bool:
        now = self._clock()
        self._until = {s: t for s, t in self._until.items() if t > now}
        return bool(self._until)


class BusyReport(BaseModel):
    source: str = Field(default="interface", max_length=64)
    busy: bool
    ttl: float = 10.0


class WakeUpdate(BaseModel):
    enabled: Optional[bool] = None
    autostart: Optional[bool] = None


def _busy_state(request: Request) -> WakeBusy:
    state = getattr(request.app.state, "wake_busy", None)
    if state is None:
        state = WakeBusy()
        request.app.state.wake_busy = state
    return state


def _status(request: Request) -> dict:
    from nicx.wake import runtime as rt

    config = getattr(request.app.state, "config", None)
    speech = getattr(config, "speech", None)
    running = rt.read_state()
    return {
        "enabled": bool(getattr(speech, "wake_word", False)),
        "running": running is not None,
        "state": (running or {}).get("state", "parado"),
        "phrases": list(getattr(speech, "wake_phrases", []) or []),
        "autostart": rt.autostart_enabled(),
        "autostart_supported": rt.startup_dir() is not None,
        "window_supported": rt.window_supported(),
        "busy": _busy_state(request).busy(),
    }


@router.get("")
async def wake_status(request: Request):
    return await asyncio.to_thread(_status, request)


@router.put("")
async def wake_update(request: Request, body: WakeUpdate):
    from nicx.wake import runtime as rt

    def apply() -> None:
        if body.enabled is not None:
            rt.set_wake_enabled(body.enabled)
            config = getattr(request.app.state, "config", None)
            speech = getattr(config, "speech", None)
            if speech is not None:
                speech.wake_word = body.enabled
            if body.enabled:
                rt.start_listener_process(only_if_enabled=True)
            else:
                rt.stop_listener()
        if body.autostart is not None:
            if not rt.set_autostart(body.autostart):
                raise HTTPException(
                    status_code=400,
                    detail="Início automático só é suportado no Windows",
                )

    try:
        await asyncio.to_thread(apply)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha ao alterar a escuta")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # A escuta leva um instante para registrar o PID.
    for _ in range(10):
        status = await asyncio.to_thread(_status, request)
        if body.enabled is None or status["running"] == body.enabled:
            break
        await asyncio.sleep(0.3)
    return status


@router.get("/busy")
async def wake_busy(request: Request):
    return {"busy": _busy_state(request).busy()}


@router.post("/busy")
async def wake_report_busy(request: Request, body: BusyReport):
    state = _busy_state(request)
    state.set(body.source, body.busy, body.ttl)
    return {"busy": state.busy()}


__all__ = ["WakeBusy", "router"]
