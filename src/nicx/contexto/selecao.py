"""Texto selecionado e texto visível de uma janela, pela acessibilidade.

UI Automation (o mesmo caminho dos leitores de tela) pelo .NET do Windows,
via ``pythonnet`` — já instalado com o app de desktop (vem com o
pywebview). Sem ele, este módulo só devolve vazio. Para cada janela:

- ``selecao``: o texto selecionado (``TextPattern.GetSelection``);
- ``documento``: o texto do documento/campo (``DocumentRange``), quando nada
  está selecionado — páginas no navegador, Word, Bloco de Notas;
- ``rotulos``: textos soltos (caixas de erro, avisos), quando não há
  documento.

Tudo roda numa thread com prazo: app travado não trava o Nicx.

Opcional (``[contexto] copiar_selecao``): quando a acessibilidade não dá
nada e a janela ainda está na frente (pedido por voz ou atalho), aperta
Ctrl+C, lê e devolve à área de transferência o texto que estava lá. Só com
texto: se havia imagem ou arquivos copiados, não mexe.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

PRAZO_S = 4.0
MAX_ELEMENTOS_TEXTO = 25
MAX_ROTULOS = 200
_ASSEMBLY = "Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35"


@dataclass(frozen=True)
class TextoDaJanela:
    selecao: str = ""
    documento: str = ""
    rotulos: str = ""


_uia: Any = None
_uia_lock = threading.Lock()


def _carregar_uia() -> Any:
    """Os tipos de UI Automation do .NET (None se não houver pythonnet)."""
    global _uia
    with _uia_lock:
        if _uia is None:
            try:
                import clr  # type: ignore[import-not-found]

                clr.AddReference(f"UIAutomationClient, {_ASSEMBLY}")
                clr.AddReference(f"UIAutomationTypes, {_ASSEMBLY}")
                from System import IntPtr  # type: ignore[import-not-found]
                from System.Windows.Automation import (  # type: ignore[import-not-found]
                    AutomationElement,
                    ControlType,
                    PropertyCondition,
                    TextPattern,
                    TreeScope,
                )

                _uia = {
                    "IntPtr": IntPtr,
                    "AutomationElement": AutomationElement,
                    "ControlType": ControlType,
                    "PropertyCondition": PropertyCondition,
                    "TextPattern": TextPattern,
                    "TreeScope": TreeScope,
                }
            except Exception:  # noqa: BLE001 - sem pythonnet/.NET: sem UIA
                logger.debug("UI Automation indisponível", exc_info=True)
                _uia = False
        return _uia or None


def disponivel() -> bool:
    return sys.platform == "win32" and _carregar_uia() is not None


def _texto_do_padrao(padrao: Any, max_caracteres: int) -> tuple[str, str]:
    selecao = ""
    try:
        intervalos = padrao.GetSelection()
        partes = [r.GetText(max_caracteres) for r in intervalos]
        selecao = "\n".join(p for p in partes if p).strip()
    except Exception:  # noqa: BLE001
        pass
    documento = ""
    if not selecao:
        try:
            documento = (padrao.DocumentRange.GetText(max_caracteres) or "").strip()
        except Exception:  # noqa: BLE001
            pass
    return selecao, documento


def _ler_uia(hwnd: int, na_frente: bool, max_caracteres: int) -> TextoDaJanela:
    uia = _carregar_uia()
    if uia is None:
        return TextoDaJanela()
    elemento_cls = uia["AutomationElement"]
    texto_cls = uia["TextPattern"]
    raiz = elemento_cls.FromHandle(uia["IntPtr"](hwnd))
    candidatos: list[Any] = []
    if na_frente:
        try:
            focado = elemento_cls.FocusedElement
            if focado is not None:
                candidatos.append(focado)
        except Exception:  # noqa: BLE001
            pass
    condicao = uia["PropertyCondition"](
        elemento_cls.IsTextPatternAvailableProperty, True
    )
    try:
        achados = raiz.FindAll(uia["TreeScope"].Subtree, condicao)
        for i in range(min(achados.Count, MAX_ELEMENTOS_TEXTO)):
            candidatos.append(achados[i])
    except Exception:  # noqa: BLE001
        pass

    documento = ""
    for elemento in candidatos:
        try:
            padrao = elemento.GetCurrentPattern(texto_cls.Pattern)
        except Exception:  # noqa: BLE001 - elemento sem TextPattern
            continue
        selecao, doc = _texto_do_padrao(padrao, max_caracteres)
        if selecao:
            return TextoDaJanela(selecao=selecao)
        if len(doc) > len(documento):
            documento = doc
    if documento:
        return TextoDaJanela(documento=documento)

    # Caixas de mensagem e avisos: só rótulos de texto.
    rotulos: list[str] = []
    try:
        condicao_texto = uia["PropertyCondition"](
            elemento_cls.ControlTypeProperty, uia["ControlType"].Text
        )
        achados = raiz.FindAll(uia["TreeScope"].Descendants, condicao_texto)
        tamanho = 0
        for i in range(min(achados.Count, MAX_ROTULOS)):
            nome = (achados[i].Current.Name or "").strip()
            if nome and nome not in rotulos:
                rotulos.append(nome)
                tamanho += len(nome)
                if tamanho >= max_caracteres:
                    break
    except Exception:  # noqa: BLE001
        pass
    return TextoDaJanela(rotulos="\n".join(rotulos))


def ler_texto_da_janela(
    hwnd: int, *, na_frente: bool, max_caracteres: int, prazo: float = PRAZO_S
) -> TextoDaJanela:
    """Seleção, documento ou rótulos da janela; vazio se nada der certo."""
    if sys.platform != "win32" or not hwnd:
        return TextoDaJanela()
    resultado: list[TextoDaJanela] = []

    def rodar() -> None:
        try:
            resultado.append(_ler_uia(hwnd, na_frente, max_caracteres))
        except Exception:  # noqa: BLE001
            logger.debug("Leitura por acessibilidade falhou", exc_info=True)

    thread = threading.Thread(target=rodar, name="nicx-contexto-uia", daemon=True)
    thread.start()
    thread.join(prazo)
    if thread.is_alive():
        logger.info("A janela demorou demais para responder à acessibilidade")
        return TextoDaJanela()
    return resultado[0] if resultado else TextoDaJanela()


# ---------------------------------------------------------------------------
# Ctrl+C (opcional)
# ---------------------------------------------------------------------------

_VK_CONTROL = 0x11
_VK_SHIFT = 0x10
_VK_MENU = 0x12
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C
_VK_C = 0x43
_KEYEVENTF_KEYUP = 0x0002
_GMEM_MOVEABLE = 0x0002
# Só formatos de texto: com eles dá para devolver o que estava copiado.
_FORMATOS_TEXTO = frozenset({1, 7, 13, 16})  # CF_TEXT, OEMTEXT, UNICODETEXT, LOCALE


def _so_texto_copiado(user32: Any) -> bool:
    from nicx.contexto.area_transferencia import abrir

    abrir(user32)
    try:
        formato = user32.EnumClipboardFormats(0)
        while formato:
            if formato not in _FORMATOS_TEXTO and formato < 0xC000:
                return False
            formato = user32.EnumClipboardFormats(formato)
        return True
    finally:
        user32.CloseClipboard()


def _gravar_texto(user32: Any, kernel32: Any, texto: Optional[str]) -> None:
    import ctypes

    from nicx.contexto.area_transferencia import CF_UNICODETEXT, abrir

    abrir(user32)
    try:
        user32.EmptyClipboard()
        if not texto:
            return
        dados = ctypes.create_unicode_buffer(texto)
        tamanho = ctypes.sizeof(dados)
        handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, tamanho)
        if not handle:
            return
        ponteiro = kernel32.GlobalLock(handle)
        ctypes.memmove(ponteiro, dados, tamanho)
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
    finally:
        user32.CloseClipboard()


def copiar_selecao(max_caracteres: int, espera_s: float = 0.8) -> str:
    """Aperta Ctrl+C na janela da frente e devolve o texto copiado.

    Devolve à área de transferência o texto que estava lá antes. Não faz
    nada se havia algo além de texto copiado ou se o usuário está segurando
    alguma tecla modificadora.
    """
    if sys.platform != "win32":
        return ""
    import ctypes
    from ctypes import wintypes

    from nicx.contexto import area_transferencia as at

    try:
        user32, kernel32 = at._win32()
        user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
        user32.EnumClipboardFormats.restype = wintypes.UINT
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.keybd_event.argtypes = [
            wintypes.BYTE,
            wintypes.BYTE,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

        for tecla in (_VK_CONTROL, _VK_SHIFT, _VK_MENU, _VK_LWIN, _VK_RWIN):
            if user32.GetAsyncKeyState(tecla) & 0x8000:
                return ""
        if not _so_texto_copiado(user32):
            return ""
        try:
            anterior = at.ler_texto_windows()
        except at.AreaProtegida:
            return ""
        antes = user32.GetClipboardSequenceNumber()
        user32.keybd_event(_VK_CONTROL, 0, 0, None)
        user32.keybd_event(_VK_C, 0, 0, None)
        user32.keybd_event(_VK_C, 0, _KEYEVENTF_KEYUP, None)
        user32.keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, None)
        limite = time.monotonic() + espera_s
        while time.monotonic() < limite:
            if user32.GetClipboardSequenceNumber() != antes:
                break
            time.sleep(0.03)
        else:
            return ""  # nada selecionado: a área de transferência não mudou
        time.sleep(0.05)
        try:
            copiado = at.ler_texto_windows() or ""
        except at.AreaProtegida:
            copiado = ""
        _gravar_texto(user32, kernel32, anterior)
        return copiado[: max_caracteres * 2]
    except Exception:  # noqa: BLE001
        logger.debug("Copiar a seleção falhou", exc_info=True)
        return ""


__all__ = [
    "TextoDaJanela",
    "copiar_selecao",
    "disponivel",
    "ler_texto_da_janela",
]
