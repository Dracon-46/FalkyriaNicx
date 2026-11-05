"""Anexos do chat.

- ``POST /v1/anexos/video`` (arquivo em ``multipart/form-data``, campo
  ``arquivo``; ``idioma`` opcional): devolve ``quadros`` (imagens em base64
  para mandar no chat), ``duracao``, ``tem_audio`` e ``transcricao`` (Whisper
  local, primeiros 3 minutos). O vídeo fica num arquivo temporário só durante
  o pedido; nada é guardado e o conteúdo não vai para o log.

As imagens não têm rota própria: vão direto no ``images`` da mensagem do chat
e são conferidas lá (:mod:`nicx.anexos.imagens`).
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/anexos", tags=["anexos"])

_PEDACO = 1024 * 1024


@router.post("/video")
async def anexar_video(
    request: Request,
    arquivo: UploadFile = File(...),
    idioma: Optional[str] = Form(default=None),
):
    from nicx.anexos import AnexoInvalido
    from nicx.anexos import video as mod_video

    sufixo = Path(arquivo.filename or "video").suffix[:10] or ".mp4"
    descritor, nome = tempfile.mkstemp(prefix="nicx-video-", suffix=sufixo)
    caminho = Path(nome)
    try:
        tamanho = 0
        with os.fdopen(descritor, "wb") as destino:
            while pedaco := await arquivo.read(_PEDACO):
                tamanho += len(pedaco)
                if tamanho > mod_video.MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="vídeo grande demais (máximo de 300 MB)",
                    )
                destino.write(pedaco)
        if tamanho == 0:
            raise HTTPException(status_code=400, detail="o vídeo veio vazio")

        fala = getattr(request.app.state, "speech_backend", None)
        transcrever = getattr(fala, "transcrever_array", None)
        lingua = (idioma or "").split("-")[0].lower() or None
        try:
            resultado = await asyncio.to_thread(
                mod_video.extrair, caminho, transcrever=transcrever, idioma=lingua
            )
        except AnexoInvalido as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "quadros": resultado.quadros,
            "duracao": round(resultado.duracao, 1),
            "tem_audio": resultado.tem_audio,
            "transcricao": resultado.transcricao,
            "transcrito": bool(transcrever) and resultado.tem_audio,
        }
    finally:
        await arquivo.close()
        try:
            caminho.unlink(missing_ok=True)
        except OSError:
            logger.debug("Arquivo temporário do vídeo não apagado", exc_info=True)


__all__ = ["router"]
