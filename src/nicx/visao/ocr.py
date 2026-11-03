"""Texto de imagens e janelas pelo OCR do próprio Windows (sem modelo, sem rede).

Roda ``ocr_windows.ps1`` (PowerShell, sem janela). A imagem fica na memória
desse processo e nunca é gravada em disco; o texto lido nunca vai para o log.
Fora do Windows, ou sem o idioma de OCR instalado, devolve ``ok=False``.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCRIPT = Path(__file__).with_name("ocr_windows.ps1")
PRAZO_SEGUNDOS = 25
_SEM_JANELA = 0x08000000  # CREATE_NO_WINDOW


@dataclass(frozen=True)
class Leitura:
    ok: bool
    texto: str = ""
    # sem_suporte, minimizada, sem_janela, sem_imagem, sem_arquivo, sem_idioma, erro
    motivo: str = ""
    linhas: int = 0


def _idioma_ocr(idioma: Optional[str]) -> str:
    from nicx.nucleo.idiomas import idioma as _idioma

    return {
        "pt-BR": "pt-BR",
        "en": "en-US",
        "es": "es-ES",
        "fr": "fr-FR",
        "zh": "zh-Hans",
        "hi": "hi-IN",
        "ar": "ar-SA",
    }.get(_idioma(idioma).codigo, "pt-BR")


def _rodar(argumentos: list[str], idioma: Optional[str]) -> Leitura:
    if sys.platform != "win32":
        return Leitura(False, motivo="sem_suporte")
    comando = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-STA",  # a área de transferência exige STA
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        *argumentos,
        "-Idioma",
        _idioma_ocr(idioma),
    ]
    try:
        saida = subprocess.run(  # noqa: S603 - script do próprio pacote, argumentos fixos
            comando,
            capture_output=True,
            timeout=PRAZO_SEGUNDOS,
            creationflags=_SEM_JANELA,
        )
        dados = json.loads(saida.stdout.decode("utf-8", errors="replace") or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        logger.info("OCR indisponível: %s", type(exc).__name__)
        return Leitura(False, motivo="erro")
    if not dados.get("ok"):
        logger.debug("OCR sem texto: %s", dados.get("motivo"))
        return Leitura(False, motivo=str(dados.get("motivo") or "erro"))
    texto = str(dados.get("texto") or "")
    logger.debug("OCR: %d linhas, %d caracteres", dados.get("linhas", 0), len(texto))
    return Leitura(
        bool(texto.strip()),
        texto=texto,
        motivo="" if texto.strip() else "vazio",
        linhas=int(dados.get("linhas") or 0),
    )


def ler_janela(hwnd: int, idioma: Optional[str] = None) -> Leitura:
    """A janela inteira, mesmo com outra na frente (PrintWindow)."""
    return _rodar(["-Modo", "janela", "-Hwnd", str(int(hwnd))], idioma)


def ler_area_transferencia(idioma: Optional[str] = None) -> Leitura:
    """A imagem copiada (print, "copiar imagem")."""
    return _rodar(["-Modo", "area"], idioma)


def ler_arquivo(caminho: Path, idioma: Optional[str] = None) -> Leitura:
    """Um arquivo de imagem (png, jpg, bmp, gif, tiff)."""
    return _rodar(
        ["-Modo", "arquivo", "-Arquivo", str(Path(caminho).resolve())], idioma
    )


__all__ = ["Leitura", "ler_area_transferencia", "ler_arquivo", "ler_janela"]
