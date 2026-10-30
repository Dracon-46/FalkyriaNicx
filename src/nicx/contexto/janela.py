"""A janela que o usuário está vendo (fora do Nicx), no Windows via ``ctypes``.

Quando o pedido vem pelo app, a janela em primeiro plano é a do próprio
Nicx; o que interessa é a última janela "de fora" que teve foco. Por isso:

1. Se a janela da frente já é de fora (pedido por voz ou atalho com o app
   de lá ainda na frente), é ela.
2. Senão, a última que o rastreador viu ganhar foco
   (``SetWinEventHook(EVENT_SYSTEM_FOREGROUND)`` numa thread do servidor).
3. Sem rastreador, a primeira janela de fora na ordem Z (a que estava logo
   abaixo do Nicx).

Ficam de fora a janela do app do Nicx (aba "Nicx" no navegador ou o app de
desktop), a janela flutuante do mascote, a barra de tarefas, o menu Iniciar
e afins. Janelas de senha e de banco são marcadas como sensíveis e não são
lidas (:func:`sensivel`).

Do título também sai o nome do arquivo aberto (VS Code, Bloco de Notas,
Word, Excel, leitores de PDF...): :func:`arquivo_no_titulo`.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
WM_QUIT = 0x0012
WM_USER = 0x0400
PM_NOREMOVE = 0x0000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GW_HWNDNEXT = 2
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14


@dataclass(frozen=True)
class InfoJanela:
    hwnd: int
    titulo: str
    processo: str  # nome do executável em minúsculas ("code.exe")
    pid: int = 0
    classe: str = ""


# ---------------------------------------------------------------------------
# Quem é do Nicx, do sistema ou sensível
# ---------------------------------------------------------------------------

# Aba do app ("Nicx", "Nicx - Microsoft Edge"), app de desktop e mascote.
_TITULO_NICX = re.compile(r"^Nicx(\s|$)")
_CLASSES_SISTEMA = frozenset(
    {
        "shell_traywnd",
        "shell_secondarytraywnd",
        "progman",
        "workerw",
        "multitaskingviewframe",
        "tasklistthumbnailwnd",
        "foregroundstaging",
        "xamlexplorerhostislandwindow",
        "windows.ui.core.corewindow",
        "notifyiconoverflowwindow",
        "topleveltaskbar",
        "#32768",
        "tooltips_class32",
    }
)
_PROCESSOS_SISTEMA = frozenset(
    {
        "searchhost.exe",
        "searchapp.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
        "lockapp.exe",
        "textinputhost.exe",
    }
)

# Gerenciadores de senha, telas de credencial do Windows e afins.
_PROCESSOS_SENSIVEIS = frozenset(
    {
        "keepass.exe",
        "keepassxc.exe",
        "1password.exe",
        "bitwarden.exe",
        "dashlane.exe",
        "lastpass.exe",
        "nordpass.exe",
        "enpass.exe",
        "roboform.exe",
        "keeper.exe",
        "keeperpasswordmanager.exe",
        "protonpass.exe",
        "pwsafe.exe",
        "credentialuibroker.exe",
        "consent.exe",
    }
)
_TITULO_SENSIVEL = re.compile(
    r"\b(?:senhas?|password\w*|passwort\w*|contrasenas?|mots? de passe|"
    r"keepass\w*|1password|bitwarden|lastpass|dashlane|nordpass|enpass|"
    r"gerenciador de senhas|cofre de senhas|internet banking|home banking|"
    r"banco(?! de dados)|bank|banking|banque|itau|bradesco|santander|nubank|"
    r"caixa economica|caixa tem|banco do brasil|sicredi|sicoob|banrisul|"
    r"btg pactual|c6 bank|mercado pago|picpay|paypal|pix|cartao de credito|"
    r"credit card|codigo de verificacao|verification code|2fa|autenticador|"
    r"authenticator)\b"
)


def _normalizar(texto: str) -> str:
    import unicodedata

    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def do_nicx(info: InfoJanela) -> bool:
    """Janela do app do Nicx, do mascote ou do próprio servidor."""
    if info.pid and info.pid == os.getpid():
        return True
    if _TITULO_NICX.match(info.titulo or ""):
        return True
    return info.processo.startswith("nicx")


def do_sistema(info: InfoJanela) -> bool:
    """Barra de tarefas, menu Iniciar, área de trabalho, menus..."""
    if not (info.titulo or "").strip():
        return True
    return (
        info.classe.lower() in _CLASSES_SISTEMA or info.processo in _PROCESSOS_SISTEMA
    )


def de_fora(info: Optional[InfoJanela]) -> bool:
    return info is not None and not do_nicx(info) and not do_sistema(info)


def sensivel(info: InfoJanela) -> bool:
    """Senhas, bancos, códigos de verificação: o Nicx não lê."""
    if info.processo in _PROCESSOS_SENSIVEIS:
        return True
    return bool(_TITULO_SENSIVEL.search(_normalizar(info.titulo)))


# ---------------------------------------------------------------------------
# Nome amigável e arquivo aberto (a partir do título)
# ---------------------------------------------------------------------------

_NOMES_APPS = {
    "code.exe": "Visual Studio Code",
    "code - insiders.exe": "Visual Studio Code",
    "cursor.exe": "Cursor",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "outlook.exe": "Outlook",
    "olk.exe": "Outlook",
    "onenote.exe": "OneNote",
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
    "acrord32.exe": "Adobe Acrobat",
    "acrobat.exe": "Adobe Acrobat",
    "sumatrapdf.exe": "SumatraPDF",
    "foxitpdfreader.exe": "Foxit PDF Reader",
    "notepad++.exe": "Notepad++",
    "sublime_text.exe": "Sublime Text",
    "windowsterminal.exe": "Terminal",
    "ms-teams.exe": "Teams",
    "teams.exe": "Teams",
    "whatsapp.exe": "WhatsApp",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
}

_SEPARADOR = re.compile(r"\s+[-–—]\s+")
_PREFIXO_MODIFICADO = re.compile(r"^[\s●•*]+")
_NOME_ARQUIVO = re.compile(r"^[^\\/:*?\"<>|]{1,200}\.[A-Za-z0-9]{1,6}$")
_CAMINHO_ABSOLUTO = re.compile(r"[A-Za-z]:\\[^:*?\"<>|]+\.[A-Za-z0-9]{1,6}")
_EXTENSOES_PADRAO = {
    "winword.exe": (".docx", ".doc", ".rtf", ".odt", ".txt"),
    "excel.exe": (".xlsx", ".xlsm", ".xls", ".csv"),
    "powerpnt.exe": (".pptx", ".ppt"),
    "acrord32.exe": (".pdf",),
    "acrobat.exe": (".pdf",),
    "sumatrapdf.exe": (".pdf",),
    "foxitpdfreader.exe": (".pdf",),
    "notepad.exe": (".txt",),
}
# Programas cujo título começa com o documento aberto.
_EDITORES = frozenset(
    {
        "code.exe",
        "code - insiders.exe",
        "cursor.exe",
        "notepad.exe",
        "notepad++.exe",
        "sublime_text.exe",
        "winword.exe",
        "excel.exe",
        "powerpnt.exe",
        "acrord32.exe",
        "acrobat.exe",
        "sumatrapdf.exe",
        "foxitpdfreader.exe",
        "wordpad.exe",
        "msedge.exe",
        "chrome.exe",
        "firefox.exe",
        "brave.exe",
    }
)
_PALAVRAS_SOLTAS = re.compile(
    r"\s*[\[(](?:modo de compatibilidade|compatibility mode|somente leitura|"
    r"read-only|administrador|administrator|salvo automaticamente|"
    r"autosaved|restricted mode|modo restrito|workspace)[\])]\s*",
    re.I,
)


@dataclass(frozen=True)
class ArquivoNoTitulo:
    nome: str  # "relatorio.docx"
    caminho: str = ""  # caminho completo, quando o título traz
    pasta_projeto: str = ""  # VS Code: a pasta aberta ("FalkyriaNicx")
    extensoes: tuple[str, ...] = ()  # nome sem extensão (Word...): candidatas


def partes_titulo(titulo: str) -> list[str]:
    titulo = _PREFIXO_MODIFICADO.sub("", titulo or "")
    titulo = _PALAVRAS_SOLTAS.sub(" ", titulo)
    return [p.strip() for p in _SEPARADOR.split(titulo) if p.strip()]


def arquivo_no_titulo(info: InfoJanela) -> Optional[ArquivoNoTitulo]:
    """O arquivo que a janela mostra, pelo título; None se não der para saber."""
    titulo = info.titulo or ""
    absoluto = _CAMINHO_ABSOLUTO.search(titulo)
    if absoluto:
        caminho = absoluto.group(0).strip()
        return ArquivoNoTitulo(PureWindowsPath(caminho).name, caminho=caminho)
    partes = partes_titulo(titulo)
    if not partes:
        return None
    processo = info.processo
    if processo not in _EDITORES and not _NOME_ARQUIVO.match(partes[0]):
        return None
    primeiro = partes[0].lstrip("*").strip()
    projeto = ""
    if (
        processo in ("code.exe", "code - insiders.exe", "cursor.exe")
        and len(partes) >= 3
    ):
        projeto = partes[1]
    if _NOME_ARQUIVO.match(primeiro):
        return ArquivoNoTitulo(primeiro, pasta_projeto=projeto)
    extensoes = _EXTENSOES_PADRAO.get(processo)
    if extensoes and len(partes) >= 2 and len(primeiro) <= 200:
        return ArquivoNoTitulo(primeiro, extensoes=extensoes)
    return None


def nome_app(info: InfoJanela, nome_explorer: str = "Explorador de Arquivos") -> str:
    if info.processo == "explorer.exe":
        return nome_explorer
    if info.processo in _NOMES_APPS:
        return _NOMES_APPS[info.processo]
    partes = partes_titulo(info.titulo)
    if len(partes) >= 2 and len(partes[-1]) <= 40:
        return partes[-1]
    base = info.processo.rsplit(".", 1)[0]
    return base[:1].upper() + base[1:] if base else (partes[0] if partes else "")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _win32() -> tuple[Any, Any, Any]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    except OSError:
        dwmapi = None
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetTopWindow.argtypes = [wintypes.HWND]
    user32.GetTopWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    return user32, kernel32, dwmapi


_cache_win32: Optional[tuple[Any, Any, Any]] = None


def _bibliotecas() -> tuple[Any, Any, Any]:
    global _cache_win32
    if _cache_win32 is None:
        _cache_win32 = _win32()
    return _cache_win32


def _nome_processo(kernel32: Any, pid: int) -> str:
    import ctypes
    from ctypes import wintypes

    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        tamanho = wintypes.DWORD(1024)
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(tamanho)
        ):
            return ""
        return PureWindowsPath(buffer.value).name.lower()
    finally:
        kernel32.CloseHandle(handle)


def info_da_janela(hwnd: int) -> Optional[InfoJanela]:
    """Título, classe e processo da janela (None se ela não existe mais)."""
    import ctypes
    from ctypes import wintypes

    if not hwnd:
        return None
    user32, kernel32, _ = _bibliotecas()
    if not user32.IsWindow(hwnd):
        return None
    tamanho = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(tamanho, 0) + 1)
    if tamanho > 0:
        user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
    classe = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, classe, 256)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return InfoJanela(
        hwnd=int(hwnd),
        titulo=buffer.value,
        processo=_nome_processo(kernel32, int(pid.value)),
        pid=int(pid.value),
        classe=classe.value,
    )


def em_primeiro_plano() -> Optional[InfoJanela]:
    if sys.platform != "win32":
        return None
    try:
        return info_da_janela(int(_bibliotecas()[0].GetForegroundWindow() or 0))
    except Exception:  # noqa: BLE001
        logger.debug("GetForegroundWindow falhou", exc_info=True)
        return None


def _escondida(user32: Any, dwmapi: Any, hwnd: int) -> bool:
    import ctypes

    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return True
    if user32.GetWindow(hwnd, GW_OWNER):
        return True
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return True
    if dwmapi is not None:
        nublada = ctypes.c_int(0)
        if (
            dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(nublada), ctypes.sizeof(nublada)
            )
            == 0
            and nublada.value
        ):
            return True
    return False


def primeira_de_fora_na_ordem_z(limite: int = 400) -> Optional[InfoJanela]:
    """A janela de fora mais à frente (a que estava logo abaixo do Nicx)."""
    if sys.platform != "win32":
        return None
    try:
        user32, _kernel32, dwmapi = _bibliotecas()
        hwnd = user32.GetTopWindow(None)
        for _ in range(limite):
            if not hwnd:
                break
            if not _escondida(user32, dwmapi, hwnd):
                info = info_da_janela(int(hwnd))
                if de_fora(info):
                    return info
            hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    except Exception:  # noqa: BLE001
        logger.debug("Ordem Z das janelas falhou", exc_info=True)
    return None


class RastreadorJanela:
    """Guarda a última janela de fora que ganhou foco.

    ``SetWinEventHook`` sem DLL (``WINEVENT_OUTOFCONTEXT``) numa thread com
    laço de mensagens; o Windows chama o callback nessa mesma thread. Para
    parar, outra thread posta ``WM_QUIT`` na fila dela.
    """

    def __init__(
        self, *, consultar: Callable[[int], Optional[InfoJanela]] = info_da_janela
    ) -> None:
        self._consultar = consultar
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._pronto = threading.Event()
        self._ultima: Optional[int] = None
        self._quando = 0.0
        self._lock = threading.Lock()
        self._user32: Any = None

    @property
    def rodando(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def ultima(self) -> Optional[int]:
        with self._lock:
            return self._ultima

    def registrar(self, hwnd: int) -> None:
        """Chamado a cada troca de foco: guarda se for janela de fora."""
        try:
            info = self._consultar(int(hwnd or 0))
        except Exception:  # noqa: BLE001
            return
        if de_fora(info):
            with self._lock:
                self._ultima = info.hwnd
                self._quando = time.monotonic()

    def iniciar(self, timeout: float = 3.0) -> bool:
        if sys.platform != "win32" or self.rodando:
            return self.rodando
        self._pronto.clear()
        self._thread = threading.Thread(
            target=self._rodar, name="nicx-contexto-janela", daemon=True
        )
        self._thread.start()
        self._pronto.wait(timeout)
        return self.rodando

    def parar(self, timeout: float = 2.0) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        if self._user32 is not None and self._thread_id:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread.join(timeout)

    def _rodar(self) -> None:
        import ctypes
        from ctypes import wintypes

        gancho = None
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            tipo_callback = ctypes.WINFUNCTYPE(
                None,
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.HWND,
                wintypes.LONG,
                wintypes.LONG,
                wintypes.DWORD,
                wintypes.DWORD,
            )
            user32.SetWinEventHook.argtypes = [
                wintypes.UINT,
                wintypes.UINT,
                wintypes.HMODULE,
                tipo_callback,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.UINT,
            ]
            user32.SetWinEventHook.restype = wintypes.HANDLE
            user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
            user32.UnhookWinEvent.restype = wintypes.BOOL
            lp_msg = ctypes.POINTER(wintypes.MSG)
            user32.GetMessageW.argtypes = [
                lp_msg,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.UINT,
            ]
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
            user32.GetForegroundWindow.restype = wintypes.HWND
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            def ao_trocar(_hook, _evento, hwnd, _obj, _filho, _thread, _tempo):
                self.registrar(int(hwnd or 0))

            callback = tipo_callback(ao_trocar)
            self._callback = callback  # vivo enquanto o gancho existir
            msg = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)
            self._thread_id = int(kernel32.GetCurrentThreadId())
            self._user32 = user32
            gancho = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND,
                EVENT_SYSTEM_FOREGROUND,
                None,
                callback,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if not gancho:
                logger.info("Rastreador de janela indisponível (SetWinEventHook)")
                return
            self.registrar(int(user32.GetForegroundWindow() or 0))
            self._pronto.set()
            while True:
                retorno = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if retorno == 0 or retorno == -1:
                    break
        except Exception:  # noqa: BLE001 - nunca derrubar o servidor
            logger.debug("Rastreador de janela parou com erro", exc_info=True)
        finally:
            if gancho:
                try:
                    user32.UnhookWinEvent(gancho)
                except Exception:  # noqa: BLE001
                    pass
            self._thread_id = 0
            self._pronto.set()


_rastreador: Optional[RastreadorJanela] = None
_rastreador_lock = threading.Lock()


def iniciar_rastreador() -> bool:
    """Sobe o rastreador (uma vez por processo). Só no Windows."""
    global _rastreador
    if sys.platform != "win32":
        return False
    with _rastreador_lock:
        if _rastreador is None:
            _rastreador = RastreadorJanela()
        return _rastreador.iniciar()


def parar_rastreador() -> None:
    with _rastreador_lock:
        if _rastreador is not None:
            _rastreador.parar()


def janela_de_fora() -> Optional[InfoJanela]:
    """A janela que o usuário estava vendo antes de falar com o Nicx."""
    if sys.platform != "win32":
        return None
    frente = em_primeiro_plano()
    if de_fora(frente):
        return frente
    rastreador = _rastreador
    if rastreador is not None:
        hwnd = rastreador.ultima()
        if hwnd:
            try:
                info = info_da_janela(hwnd)
            except Exception:  # noqa: BLE001
                info = None
            if de_fora(info):
                return info
    return primeira_de_fora_na_ordem_z()


def esta_na_frente(info: InfoJanela) -> bool:
    frente = em_primeiro_plano()
    return frente is not None and frente.hwnd == info.hwnd


__all__ = [
    "ArquivoNoTitulo",
    "InfoJanela",
    "RastreadorJanela",
    "arquivo_no_titulo",
    "de_fora",
    "do_nicx",
    "do_sistema",
    "em_primeiro_plano",
    "esta_na_frente",
    "iniciar_rastreador",
    "janela_de_fora",
    "nome_app",
    "parar_rastreador",
    "partes_titulo",
    "primeira_de_fora_na_ordem_z",
    "sensivel",
]
