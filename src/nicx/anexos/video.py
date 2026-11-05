"""Vídeo anexado: alguns quadros e o que se fala nele.

O modelo local enxerga imagens, não vídeo. Então o vídeo vira
:data:`QUADROS` quadros espalhados pela duração (reduzidos como as imagens)
e, se tiver som, a transcrição dos primeiros :data:`MAX_SEGUNDOS_AUDIO`
segundos pelo Whisper local. O PyAV (que o faster-whisper já usa) abre o
arquivo; nada sai do PC.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from nicx.anexos import AnexoInvalido
from nicx.anexos.imagens import LADO

logger = logging.getLogger(__name__)

QUADROS = 4
MAX_SEGUNDOS_AUDIO = 180
MAX_BYTES = 300 * 1024 * 1024
_TAXA = 16000
# Depois de pular para perto do ponto, quantos quadros decodificar no máximo
# até chegar nele (vídeo sem quadros-chave não pode travar o PC).
_MAX_DECODIFICADOS = 240


@dataclass
class Video:
    quadros: list[str] = field(default_factory=list)
    duracao: float = 0.0
    tem_audio: bool = False
    transcricao: str = ""


def _jpeg(frame, lado: int) -> str:
    import base64

    img = frame.to_image()
    img.thumbnail((lado, lado))
    saida = io.BytesIO()
    img.convert("RGB").save(saida, "JPEG", quality=85)
    return base64.b64encode(saida.getvalue()).decode("ascii")


def _quadros(caminho: Path, quantos: int, lado: int) -> tuple[list[str], float, bool]:
    import av

    try:
        conteiner = av.open(str(caminho))
    except Exception as exc:  # noqa: BLE001 - PyAV tem várias exceções próprias
        raise AnexoInvalido("não consegui abrir o vídeo") from exc
    with conteiner:
        if not conteiner.streams.video:
            raise AnexoInvalido("o arquivo não tem imagem de vídeo")
        fluxo = conteiner.streams.video[0]
        fluxo.thread_type = "AUTO"
        if fluxo.duration and fluxo.time_base:
            duracao = float(fluxo.duration * fluxo.time_base)
        elif conteiner.duration:
            duracao = conteiner.duration / 1_000_000
        else:
            duracao = 0.0
        tem_audio = bool(conteiner.streams.audio)
        alvos = (
            [duracao * (i + 0.5) / quantos for i in range(quantos)]
            if duracao > 0
            else [0.0]
        )
        imagens: list[str] = []
        for alvo in alvos:
            try:
                if fluxo.time_base:
                    conteiner.seek(
                        int(alvo / fluxo.time_base), stream=fluxo, backward=True
                    )
            except Exception:  # noqa: BLE001 - sem índice: decodifica do começo
                logger.debug("seek falhou no vídeo", exc_info=True)
            escolhido = None
            for i, frame in enumerate(conteiner.decode(fluxo)):
                escolhido = frame
                chegou = frame.time is None or frame.time >= alvo - 0.05
                if chegou or i >= _MAX_DECODIFICADOS:
                    break
            if escolhido is not None:
                imagens.append(_jpeg(escolhido, lado))
    if not imagens:
        raise AnexoInvalido("não consegui ler nenhum quadro do vídeo")
    return imagens, duracao, tem_audio


def audio_16k(caminho: Path, limite_s: int = MAX_SEGUNDOS_AUDIO):
    """Os primeiros *limite_s* segundos do som, mono a 16 kHz (float32)."""
    import av
    import numpy as np

    with av.open(str(caminho)) as conteiner:
        if not conteiner.streams.audio:
            return None
        conversor = av.AudioResampler(format="flt", layout="mono", rate=_TAXA)
        partes = []
        total = 0
        limite = limite_s * _TAXA
        for frame in conteiner.decode(conteiner.streams.audio[0]):
            for convertido in conversor.resample(frame):
                pedaco = convertido.to_ndarray().reshape(-1)
                partes.append(pedaco)
                total += pedaco.size
            if total >= limite:
                break
    if not partes:
        return None
    return np.concatenate(partes)[:limite].astype(np.float32)


def extrair(
    caminho: Path,
    *,
    quadros: int = QUADROS,
    lado: int = LADO,
    transcrever: Optional[Callable[..., str]] = None,
    idioma: Optional[str] = None,
) -> Video:
    """Quadros do vídeo e, com *transcrever*, o que se fala nele."""
    caminho = Path(caminho)
    if caminho.stat().st_size > MAX_BYTES:
        raise AnexoInvalido("vídeo grande demais (máximo de 300 MB)")
    imagens, duracao, tem_audio = _quadros(caminho, max(1, quadros), lado)
    video = Video(quadros=imagens, duracao=duracao, tem_audio=tem_audio)
    if tem_audio and transcrever is not None:
        try:
            som = audio_16k(caminho)
            if som is not None and som.size:
                video.transcricao = (transcrever(som, language=idioma) or "").strip()
        except Exception:  # noqa: BLE001 - sem transcrição, os quadros ainda servem
            logger.warning("Não consegui transcrever o áudio do vídeo", exc_info=True)
    return video


__all__ = ["MAX_BYTES", "QUADROS", "Video", "audio_16k", "extrair"]
