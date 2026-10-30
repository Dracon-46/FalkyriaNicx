"""Lê o texto da área de transferência do Windows. Só leitura: nunca grava.

Usa ``ctypes`` (user32/kernel32), sem dependência nova. Em macOS/Linux
devolve ``Leitura(motivo="sem_suporte")``.

Gerenciadores de senha (KeePass, 1Password, Bitwarden...) marcam o que
copiam com formatos especiais para que leitores de área de transferência
ignorem o conteúdo; quando um deles está presente, o Nicx não lê.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable, Optional

from nicx.contexto.montagem import Leitura, ler_limitado

logger = logging.getLogger(__name__)

CF_UNICODETEXT = 13
# Formatos que gerenciadores de senha põem junto com o que copiam.
FORMATOS_PROTEGIDOS = (
    "ExcludeClipboardContentFromMonitorProcessing",
    "Clipboard Viewer Ignore",
)
# Nada de ler 100 MB por engano: o corte fino vem depois.
MAX_BRUTO = 2_000_000

SEM_SUPORTE = "sem_suporte"
VAZIO = "vazio"
PROTEGIDO = "protegido"
OCUPADA = "ocupada"
ERRO = "erro"


class AreaProtegida(Exception):
    """O conteúdo veio de um gerenciador de senhas."""


class AreaOcupada(Exception):
    """Outro programa está com a área de transferência aberta."""


def _win32() -> tuple[Any, Any]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.GetClipboardSequenceNumber.argtypes = []
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    return user32, kernel32


def _protegido(user32: Any) -> bool:
    for nome in FORMATOS_PROTEGIDOS:
        formato = user32.RegisterClipboardFormatW(nome)
        if formato and user32.IsClipboardFormatAvailable(formato):
            return True
    return False


def abrir(user32: Any, tentativas: int = 8) -> None:
    """Abre a área de transferência; outro programa pode estar com ela."""
    for _ in range(tentativas):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise AreaOcupada()


def ler_texto_windows() -> Optional[str]:
    """O texto bruto (CF_UNICODETEXT) ou None se não houver texto."""
    import ctypes

    user32, kernel32 = _win32()
    if _protegido(user32):
        raise AreaProtegida()
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    abrir(user32)
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ponteiro = kernel32.GlobalLock(handle)
        if not ponteiro:
            return None
        try:
            caracteres = min(int(kernel32.GlobalSize(handle)) // 2, MAX_BRUTO)
            texto = ctypes.wstring_at(ponteiro, caracteres) if caracteres else ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    return texto.split("\x00", 1)[0]


def sequencia() -> int:
    """Número que muda a cada cópia (0 fora do Windows)."""
    if sys.platform != "win32":
        return 0
    try:
        return int(_win32()[0].GetClipboardSequenceNumber())
    except Exception:  # noqa: BLE001
        return 0


def ler(
    max_caracteres: int = 20000,
    *,
    plataforma: str = sys.platform,
    leitor: Optional[Callable[[], Optional[str]]] = None,
) -> Leitura:
    """Lê o texto copiado, limpo e cortado em *max_caracteres*.

    Nunca loga o conteúdo; só o motivo quando não dá para ler.
    """
    if plataforma != "win32" and leitor is None:
        return Leitura(motivo=SEM_SUPORTE)
    try:
        bruto = (leitor or ler_texto_windows)()
    except AreaProtegida:
        logger.info("Área de transferência com conteúdo de gerenciador de senhas")
        return Leitura(motivo=PROTEGIDO)
    except AreaOcupada:
        return Leitura(motivo=OCUPADA)
    except Exception:  # noqa: BLE001 - nunca derrubar o chat
        logger.debug("Falha ao ler a área de transferência", exc_info=True)
        return Leitura(motivo=ERRO)
    if not bruto:
        return Leitura(motivo=VAZIO)
    return ler_limitado(bruto, max_caracteres)


__all__ = [
    "CF_UNICODETEXT",
    "ERRO",
    "OCUPADA",
    "PROTEGIDO",
    "SEM_SUPORTE",
    "VAZIO",
    "AreaOcupada",
    "AreaProtegida",
    "ler",
    "ler_texto_windows",
    "sequencia",
]
