"""Digita o texto do ditado na janela que estava em foco (Windows, ``ctypes``).

Cada caractere vai como tecla Unicode (``SendInput`` com
``KEYEVENTF_UNICODE``): funciona em qualquer layout de teclado e com acentos,
sem passar pela área de transferência (o que o usuário copiou fica intacto).
A quebra de linha vai como Shift+Enter, que pula linha nos editores e não
envia a mensagem em programas de chat.

Antes de digitar: espera o usuário soltar Ctrl/Alt/Shift/Win (senão o texto
viraria atalhos) e devolve o foco à janela guardada no momento do atalho. Se
o foco não voltar, nada é digitado.

Limite do Windows: programas abertos como administrador não aceitam teclas de
um programa comum (UIPI) e o Windows não avisa quando isso acontece.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
_MODIFICADORES = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)
_SW_RESTORE = 9

# Eventos por chamada ao SendInput; pausa curta entre lotes para o programa
# de destino acompanhar.
LOTE = 64
PAUSA_LOTE_S = 0.005

# (vk, scan, flags) de um evento de teclado.
Evento = tuple[int, int, int]


def eventos_para(texto: str) -> list[Evento]:
    """Eventos de teclado (aperta/solta) que digitam *texto*. Puro."""
    eventos: list[Evento] = []
    for caractere in texto.replace("\r\n", "\n").replace("\r", "\n"):
        if caractere == "\n":
            eventos += [
                (VK_SHIFT, 0, 0),
                (VK_RETURN, 0, 0),
                (VK_RETURN, 0, KEYEVENTF_KEYUP),
                (VK_SHIFT, 0, KEYEVENTF_KEYUP),
            ]
            continue
        dados = caractere.encode("utf-16-le")
        # Fora do plano básico (emoji): dois "caracteres" UTF-16 (surrogates).
        for i in range(0, len(dados), 2):
            unidade = int.from_bytes(dados[i : i + 2], "little")
            eventos.append((0, unidade, KEYEVENTF_UNICODE))
            eventos.append((0, unidade, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    return eventos


@functools.lru_cache(maxsize=1)
def _estruturas() -> tuple[Any, Any]:
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    # A união precisa do tamanho do maior membro (MOUSEINPUT), senão o
    # SendInput recusa tudo por cbSize errado.
    class _UNIAO(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _UNIAO)]

    return INPUT, KEYBDINPUT


@functools.lru_cache(maxsize=1)
def _win32() -> tuple[Any, Any]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    input_t, _ = _estruturas()
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(input_t), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    return user32, kernel32


def tecla_apertada(vk: int) -> bool:
    """A tecla *vk* está apertada agora (modo "segurar" do ditado)."""
    user32, _ = _win32()
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class DigitadorWindows:
    """Guarda a janela em foco e digita nela depois."""

    def __init__(
        self,
        *,
        win32: Optional[tuple[Any, Any]] = None,
        enviar: Optional[Callable[[list[Evento]], int]] = None,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._win32_fixo = win32
        self._enviar_fixo = enviar
        self._dormir = dormir
        self._relogio = relogio

    @property
    def _api(self) -> tuple[Any, Any]:
        return self._win32_fixo or _win32()

    def janela_em_foco(self) -> int:
        user32, _ = self._api
        return int(user32.GetForegroundWindow() or 0)

    def esperar_modificadores(self, prazo_s: float = 3.0) -> bool:
        """Espera Ctrl/Alt/Shift/Win soltos; False se o prazo acabou."""
        user32, _ = self._api
        fim = self._relogio() + prazo_s
        while True:
            if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFICADORES):
                return True
            if self._relogio() >= fim:
                return False
            self._dormir(0.03)

    def focar(self, hwnd: int) -> bool:
        """Devolve o foco a *hwnd*; True se ela ficou em primeiro plano."""
        user32, kernel32 = self._api
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        if int(user32.GetForegroundWindow() or 0) == hwnd:
            return True
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, _SW_RESTORE)
        if not user32.SetForegroundWindow(hwnd):
            # O Windows só deixa trocar o foco quem recebeu a última entrada;
            # "pegar carona" na fila da janela da frente resolve.
            frente = int(user32.GetForegroundWindow() or 0)
            minha = int(kernel32.GetCurrentThreadId())
            dela = int(user32.GetWindowThreadProcessId(frente, None)) if frente else 0
            ligado = bool(
                dela and dela != minha and user32.AttachThreadInput(minha, dela, True)
            )
            try:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            finally:
                if ligado:
                    user32.AttachThreadInput(minha, dela, False)
        self._dormir(0.05)
        return int(user32.GetForegroundWindow() or 0) == hwnd

    def _enviar(self, eventos: list[Evento]) -> int:
        if self._enviar_fixo is not None:
            return self._enviar_fixo(eventos)
        import ctypes

        user32, _ = self._api
        input_t, _keybd = _estruturas()
        lista = (input_t * len(eventos))()
        for item, (vk, scan, flags) in zip(lista, eventos):
            item.type = INPUT_KEYBOARD
            item.ki.wVk = vk
            item.ki.wScan = scan
            item.ki.dwFlags = flags
            item.ki.time = 0
            item.ki.dwExtraInfo = 0
        return int(user32.SendInput(len(eventos), lista, ctypes.sizeof(input_t)))

    def digitar(self, texto: str, hwnd: int) -> bool:
        """Digita *texto* em *hwnd*. False se o foco não voltou ou o Windows
        recusou as teclas (nesse caso nada, ou só parte, foi digitado)."""
        if not texto:
            return True
        if not self.esperar_modificadores():
            logger.info(
                "Ditado: Ctrl/Alt/Shift/Win ainda apertados; digitando assim mesmo"
            )
        if not self.focar(hwnd):
            logger.warning(
                "Ditado: não foi possível voltar para a janela de origem; "
                "nada foi digitado"
            )
            return False
        eventos = eventos_para(texto)
        for inicio in range(0, len(eventos), LOTE):
            lote = eventos[inicio : inicio + LOTE]
            if self._enviar(lote) != len(lote):
                logger.warning("Ditado: o Windows recusou parte das teclas")
                return False
            if inicio + LOTE < len(eventos):
                self._dormir(PAUSA_LOTE_S)
        return True


__all__ = [
    "KEYEVENTF_KEYUP",
    "KEYEVENTF_UNICODE",
    "VK_RETURN",
    "VK_SHIFT",
    "DigitadorWindows",
    "eventos_para",
    "tecla_apertada",
]
