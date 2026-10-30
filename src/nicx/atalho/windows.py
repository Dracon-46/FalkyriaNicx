"""Atalho global no Windows só com ``ctypes``: ``RegisterHotKey`` e um laço de
mensagens numa thread daemon, mais o necessário para achar e focar janelas.

O atalho é registrado sem janela (``hWnd = NULL``): o Windows manda o
``WM_HOTKEY`` para a fila da própria thread que registrou, por isso registro,
laço e ``UnregisterHotKey`` acontecem todos nela. Uma thread só
(:class:`LacoAtalhos`) atende todos os atalhos do Nicx (chamar o Nicx, ditado),
cada um com seu id; os pedidos de registrar/remover chegam por uma mensagem
própria e a thread sai sozinha quando não sobra atalho. Para sair antes,
outra thread posta ``WM_QUIT`` nessa fila.

As bibliotecas do sistema podem ser trocadas (``win32=``) para testar sem
registrar atalho de verdade.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from nicx.atalho.teclas import Combinacao

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_USER = 0x0400
WM_APP = 0x8000
WM_NICX_PEDIDO = WM_APP + 0x4E  # "registre/remova um atalho" (só nesta fila)
PM_NOREMOVE = 0x0000
MOD_NOREPEAT = 0x4000  # segurar as teclas não dispara várias vezes
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
HOTKEY_ID = 0x4E58  # "NX"; só precisa ser único nesta thread
HOTKEY_ID_DITADO = 0x4E44  # "ND": ditado universal

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


@dataclass
class _Pedido:
    tipo: str  # "registrar" ou "remover"
    ident: int
    combinacao: Optional[Combinacao] = None
    ao_apertar: Optional[Callable[[], None]] = None
    feito: threading.Event = field(default_factory=threading.Event)
    resultado: ResultadoRegistro = ResultadoRegistro(False, 0, "não atendido")


@dataclass
class _Registro:
    combinacao: Combinacao
    ao_apertar: Callable[[], None]
    ultimo_toque: float = float("-inf")


class LacoAtalhos:
    """Uma thread com laço de mensagens para todos os atalhos (ids distintos).

    Sobe no primeiro :meth:`registrar` e sai sozinha quando o último atalho é
    removido. Registro e remoção acontecem sempre na thread do laço, como o
    Windows exige.
    """

    def __init__(
        self,
        *,
        win32: Optional[Win32] = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._win32 = win32
        self._relogio = relogio
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._user32: Any = None
        self._pronto = threading.Event()
        self._falha_inicio = ""
        self._saindo = False
        self._pedidos: "queue.Queue[_Pedido]" = queue.Queue()
        self._registros: dict[int, _Registro] = {}  # só a thread do laço mexe

    # -- API ---------------------------------------------------------------
    def registrar(
        self,
        ident: int,
        combinacao: Combinacao,
        ao_apertar: Callable[[], None],
        timeout: float = 3.0,
    ) -> ResultadoRegistro:
        return self._enviar(
            _Pedido("registrar", ident, combinacao, ao_apertar), timeout
        )

    def remover(self, ident: int, timeout: float = 2.0) -> None:
        with self._lock:
            if not self._vivo():
                return
        self._enviar(_Pedido("remover", ident), timeout)

    def parar(self, timeout: float = 2.0) -> None:
        """Tira todos os atalhos e encerra a thread."""
        with self._lock:
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

    # -- envio de pedidos --------------------------------------------------
    def _vivo(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._saindo

    def _garantir_thread(self, timeout: float) -> bool:
        """Com ``_lock`` na mão: thread do laço de pé e pronta para pedidos."""
        if self._vivo():
            return True
        anterior = self._thread
        if anterior is not None and anterior.is_alive():
            anterior.join(timeout)  # já decidiu sair; não precisa do _lock
        self._saindo = False
        self._falha_inicio = ""
        self._pronto.clear()
        self._thread = threading.Thread(
            target=self._rodar, name="nicx-atalho-teclado", daemon=True
        )
        self._thread.start()
        if not self._pronto.wait(timeout):
            self._falha_inicio = "O Windows não respondeu ao registro."
        return not self._falha_inicio

    def _enviar(self, pedido: _Pedido, timeout: float) -> ResultadoRegistro:
        with self._lock:
            if not self._garantir_thread(timeout):
                return ResultadoRegistro(False, 0, self._falha_inicio)
            self._pedidos.put(pedido)
            self._user32.PostThreadMessageW(self._thread_id, WM_NICX_PEDIDO, 0, 0)
        if not pedido.feito.wait(timeout):
            return ResultadoRegistro(False, 0, "O Windows não respondeu ao registro.")
        return pedido.resultado

    # -- thread ------------------------------------------------------------
    def _rodar(self) -> None:
        import ctypes

        try:
            user32, kernel32, ultimo_erro = self._win32 or carregar_win32()
            self._user32 = user32
            msg = _novo_msg()
            # Cria a fila de mensagens antes de alguém postar nela.
            user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)
            self._thread_id = int(kernel32.GetCurrentThreadId())
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o servidor
            logger.exception("Falha ao preparar o atalho de teclado")
            self._falha_inicio = str(exc) or "Falha ao preparar o atalho de teclado."
            self._saindo = True
            self._pronto.set()
            return

        self._pronto.set()
        try:
            while True:
                retorno = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if retorno == 0 or retorno == -1:  # WM_QUIT ou erro
                    break
                if msg.message == WM_HOTKEY:
                    self._disparar(int(msg.wParam))
                elif msg.message == WM_NICX_PEDIDO:
                    self._atender(user32, ultimo_erro)
                    with self._lock:
                        if not self._registros and self._pedidos.empty():
                            self._saindo = True
                            break
        except Exception:  # noqa: BLE001
            logger.exception("O laço do atalho de teclado parou com erro")
        finally:
            self._saindo = True
            for ident in list(self._registros):
                try:
                    user32.UnregisterHotKey(None, ident)
                except Exception:  # noqa: BLE001
                    logger.debug("UnregisterHotKey falhou", exc_info=True)
            self._registros.clear()
            # Quem ainda esperava um pedido não fica pendurado.
            while True:
                try:
                    pedido = self._pedidos.get_nowait()
                except queue.Empty:
                    break
                pedido.resultado = ResultadoRegistro(False, 0, "Atalhos encerrados.")
                pedido.feito.set()
            self._thread_id = 0

    def _atender(self, user32: Any, ultimo_erro: Callable[[], int]) -> None:
        while True:
            try:
                pedido = self._pedidos.get_nowait()
            except queue.Empty:
                return
            try:
                if pedido.tipo == "registrar":
                    pedido.resultado = self._registrar_aqui(user32, ultimo_erro, pedido)
                else:
                    if self._registros.pop(pedido.ident, None) is not None:
                        user32.UnregisterHotKey(None, pedido.ident)
                    pedido.resultado = ResultadoRegistro(True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha ao registrar o atalho de teclado")
                pedido.resultado = ResultadoRegistro(False, 0, str(exc))
            finally:
                pedido.feito.set()

    def _registrar_aqui(
        self, user32: Any, ultimo_erro: Callable[[], int], pedido: _Pedido
    ) -> ResultadoRegistro:
        assert pedido.combinacao is not None and pedido.ao_apertar is not None
        if self._registros.pop(pedido.ident, None) is not None:
            user32.UnregisterHotKey(None, pedido.ident)
        ok = user32.RegisterHotKey(
            None,
            pedido.ident,
            pedido.combinacao.bits_modificadores | MOD_NOREPEAT,
            pedido.combinacao.codigo_virtual,
        )
        if not ok:
            erro = int(ultimo_erro() or 0)
            if erro == ERROR_HOTKEY_ALREADY_REGISTERED:
                texto = "A combinação já está em uso por outro programa."
            else:
                texto = f"O Windows recusou o atalho (erro {erro})."
            return ResultadoRegistro(False, erro, texto)
        self._registros[pedido.ident] = _Registro(pedido.combinacao, pedido.ao_apertar)
        return ResultadoRegistro(True)

    def _disparar(self, ident: int) -> None:
        registro = self._registros.get(ident)
        if registro is None:
            return
        agora = self._relogio()
        if agora - registro.ultimo_toque < INTERVALO_MINIMO_S:
            return
        registro.ultimo_toque = agora
        logger.info("Atalho %s apertado", registro.combinacao.rotulo)
        ao_apertar = registro.ao_apertar

        def executar() -> None:
            try:
                ao_apertar()
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao executar a ação do atalho de teclado")

        # Fora do laço: abrir janela/navegador não pode atrasar o próximo toque.
        threading.Thread(target=executar, name="nicx-atalho-acao", daemon=True).start()


_laco_global: Optional[LacoAtalhos] = None
_laco_global_lock = threading.Lock()


def laco_compartilhado() -> LacoAtalhos:
    """O laço único do servidor: atalho do Nicx e ditado na mesma thread."""
    global _laco_global
    with _laco_global_lock:
        if _laco_global is None:
            _laco_global = LacoAtalhos()
        return _laco_global


class EscutaAtalho:
    """Registra *combinacao* (id *ident*) e chama *ao_apertar* a cada toque.

    Sem *laco*, usa um laço só seu (encerrado em :meth:`parar`).
    """

    def __init__(
        self,
        combinacao: Combinacao,
        ao_apertar: Callable[[], None],
        *,
        ident: int = HOTKEY_ID,
        laco: Optional[LacoAtalhos] = None,
        win32: Optional[Win32] = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.combinacao = combinacao
        self.ident = ident
        self._ao_apertar = ao_apertar
        self._proprio = laco is None
        self._laco = laco or LacoAtalhos(win32=win32, relogio=relogio)
        self._registrado = False

    def iniciar(self, timeout: float = 3.0) -> ResultadoRegistro:
        resultado = self._laco.registrar(
            self.ident, self.combinacao, self._ao_apertar, timeout
        )
        self._registrado = resultado.ok
        return resultado

    def parar(self, timeout: float = 2.0) -> None:
        if self._registrado:
            self._registrado = False
            self._laco.remover(self.ident, timeout)
        if self._proprio:
            self._laco.parar(timeout)

    @property
    def rodando(self) -> bool:
        return self._registrado and self._laco.rodando


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
    "HOTKEY_ID_DITADO",
    "MOD_NOREPEAT",
    "WM_HOTKEY",
    "WM_NICX_PEDIDO",
    "WM_QUIT",
    "EscutaAtalho",
    "LacoAtalhos",
    "ResultadoRegistro",
    "carregar_win32",
    "laco_compartilhado",
    "focar",
    "listar_janelas",
    "permitir_foco_de_outros",
]
