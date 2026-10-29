"""Atalho global no Windows só com ``ctypes``: ``RegisterHotKey`` e um laço de
mensagens numa thread daemon, mais o necessário para achar e focar janelas.

O atalho é registrado sem janela (``hWnd = NULL``): o Windows manda o
``WM_HOTKEY`` para a fila da própria thread que registrou, por isso registro,
laço e ``UnregisterHotKey`` acontecem todos nela. Para sair, outra thread
posta ``WM_QUIT`` nessa fila.

As bibliotecas do sistema podem ser trocadas (``win32=``) para testar sem
registrar atalho de verdade.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from nicx.atalho.teclas import Combinacao

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_USER = 0x0400
PM_NOREMOVE = 0x0000
MOD_NOREPEAT = 0x4000  # segurar as teclas não dispara várias vezes
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
HOTKEY_ID = 0x4E58  # "NX"; só precisa ser único nesta thread

# Dois toques muito seguidos (tecla presa, mão pesada) contam como um.
INTERVALO_MINIMO_S = 0.8

# (user32, kernel32, get_last_error)
Win32 = tuple[Any, Any, Callable[[], int]]


@dataclass(frozen=True, slots=True)
class ResultadoRegistro:
    ok: bool
    erro: int = 0
    mensagem: str = ""

    @property
    def em_uso(self) -> bool:
        return self.erro == ERROR_HOTKEY_ALREADY_REGISTERED


def carregar_win32() -> Win32:
    """user32/kernel32 com as assinaturas usadas aqui (instâncias próprias,
    para não mexer nas de outros módulos)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lp_msg = ctypes.POINTER(wintypes.MSG)

    user32.RegisterHotKey.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [lp_msg, wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [
        lp_msg,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostThreadMessageW.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    return user32, kernel32, ctypes.get_last_error


def _novo_msg() -> Any:
    from ctypes import wintypes

    return wintypes.MSG()


class EscutaAtalho:
    """Registra *combinacao* e chama *ao_apertar* a cada toque."""

    def __init__(
        self,
        combinacao: Combinacao,
        ao_apertar: Callable[[], None],
        *,
        win32: Optional[Win32] = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.combinacao = combinacao
        self._ao_apertar = ao_apertar
        self._win32 = win32
        self._relogio = relogio
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._pronto = threading.Event()
        self._resultado = ResultadoRegistro(False, 0, "não iniciado")
        self._ultimo_toque = float("-inf")
        self._user32: Any = None

    # -- ciclo de vida -----------------------------------------------------
    def iniciar(self, timeout: float = 3.0) -> ResultadoRegistro:
        """Sobe a thread e espera o resultado do registro."""
        self._pronto.clear()
        self._thread = threading.Thread(
            target=self._rodar, name="nicx-atalho-teclado", daemon=True
        )
        self._thread.start()
        if not self._pronto.wait(timeout):
            return ResultadoRegistro(False, 0, "O Windows não respondeu ao registro.")
        return self._resultado

    def parar(self, timeout: float = 2.0) -> None:
        """Pede o fim do laço; a própria thread tira o registro."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        if self._user32 is not None and self._thread_id:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread.join(timeout)
        if thread.is_alive():
            logger.warning("A escuta do atalho de teclado não parou a tempo")

    @property
    def rodando(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- thread ------------------------------------------------------------
    def _rodar(self) -> None:
        import ctypes

        try:
            user32, kernel32, ultimo_erro = self._win32 or carregar_win32()
            self._user32 = user32
            msg = _novo_msg()
            # Cria a fila de mensagens antes de alguém postar WM_QUIT nela.
            user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)
            self._thread_id = int(kernel32.GetCurrentThreadId())
            ok = user32.RegisterHotKey(
                None,
                HOTKEY_ID,
                self.combinacao.bits_modificadores | MOD_NOREPEAT,
                self.combinacao.codigo_virtual,
            )
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o servidor
            logger.exception("Falha ao preparar o atalho de teclado")
            self._resultado = ResultadoRegistro(False, 0, str(exc))
            self._pronto.set()
            return

        if not ok:
            erro = int(ultimo_erro() or 0)
            if erro == ERROR_HOTKEY_ALREADY_REGISTERED:
                texto = "A combinação já está em uso por outro programa."
            else:
                texto = f"O Windows recusou o atalho (erro {erro})."
            self._resultado = ResultadoRegistro(False, erro, texto)
            self._pronto.set()
            return

        self._resultado = ResultadoRegistro(True)
        self._pronto.set()
        try:
            while True:
                retorno = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if retorno == 0 or retorno == -1:  # WM_QUIT ou erro
                    break
                if msg.message == WM_HOTKEY and int(msg.wParam) == HOTKEY_ID:
                    self._disparar()
        except Exception:  # noqa: BLE001
            logger.exception("O laço do atalho de teclado parou com erro")
        finally:
            try:
                user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:  # noqa: BLE001
                logger.debug("UnregisterHotKey falhou", exc_info=True)
            self._thread_id = 0

    def _disparar(self) -> None:
        agora = self._relogio()
        if agora - self._ultimo_toque < INTERVALO_MINIMO_S:
            return
        self._ultimo_toque = agora
        logger.info("Atalho %s apertado", self.combinacao.rotulo)

        def executar() -> None:
            try:
                self._ao_apertar()
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao executar a ação do atalho de teclado")

        # Fora do laço: abrir janela/navegador não pode atrasar o próximo toque.
        threading.Thread(target=executar, name="nicx-atalho-acao", daemon=True).start()


# ---------------------------------------------------------------------------
# Janelas: achar e trazer para a frente
# ---------------------------------------------------------------------------

_ASFW_ANY = -1
_SW_RESTORE = 9


def _user32_janelas() -> Any:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = [
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
        wintypes.LPARAM,
    ]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    return user32


def listar_janelas() -> list[tuple[int, int, str]]:
    """Janelas visíveis com título: (hwnd, pid, título)."""
    import ctypes
    from ctypes import wintypes

    user32 = _user32_janelas()
    janelas: list[tuple[int, int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visitar(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        tamanho = user32.GetWindowTextLengthW(hwnd)
        if tamanho <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(tamanho + 1)
        user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        janelas.append((int(hwnd), int(pid.value), buffer.value))
        return True

    user32.EnumWindows(visitar, 0)
    return janelas


def focar(hwnd: int) -> bool:
    """Restaura (se minimizada) e traz a janela para a frente."""
    user32 = _user32_janelas()
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, _SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))


def permitir_foco_de_outros() -> None:
    """Deixa a janela que vamos abrir (outro processo) vir para a frente.

    Quem recebeu o atalho pode trazer janelas à frente; o processo filho, não,
    a menos que receba essa permissão.
    """
    try:
        _user32_janelas().AllowSetForegroundWindow(_ASFW_ANY & 0xFFFFFFFF)
    except Exception:  # noqa: BLE001
        logger.debug("AllowSetForegroundWindow falhou", exc_info=True)


__all__ = [
    "ERROR_HOTKEY_ALREADY_REGISTERED",
    "HOTKEY_ID",
    "MOD_NOREPEAT",
    "WM_HOTKEY",
    "WM_QUIT",
    "EscutaAtalho",
    "ResultadoRegistro",
    "carregar_win32",
    "focar",
    "listar_janelas",
    "permitir_foco_de_outros",
]
