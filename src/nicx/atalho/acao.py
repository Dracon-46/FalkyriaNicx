"""O que o atalho faz: abrir o mascote flutuante ouvindo, ou abrir o app.

Reaproveita as peças do "Nicx, ligar" (:mod:`nicx.voz.escuta.runtime`): a
janela flutuante é o mesmo processo ``nicx.voz.escuta.window`` com a rota
``/flutuante`` (que já começa a ouvir sozinha) e o plano B é o navegador.
Sempre uma janela só: se ela já estiver aberta, é trazida para a frente.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading
import webbrowser
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ACOES = ("flutuante", "app")

# Linha de comando do processo da janela do mascote.
_MODULO_JANELA = "nicx.voz.escuta.window"

# A aba do app tem o título "Nicx"; o navegador acrescenta " - Microsoft Edge",
# " e mais 2 páginas"... A janela do mascote também se chama "Nicx", mas é um
# processo Python e fica de fora.
_TITULO_APP = re.compile(r"^Nicx(\s|$)")
_NAVEGADORES = frozenset(
    {
        "msedge.exe",
        "chrome.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
        "vivaldi.exe",
        "chromium.exe",
    }
)


def _base_padrao() -> str:
    from nicx.voz.escuta import runtime as rt

    return rt.server_base_url()


def _nome_processo(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name().lower()
    except Exception:  # noqa: BLE001
        return ""


def _processos_do_mascote() -> set[int]:
    """PIDs de janelas do mascote abertas por qualquer processo (escuta, atalho)."""
    try:
        import psutil
    except Exception:  # noqa: BLE001
        return set()
    pids: set[int] = set()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
        except Exception:  # noqa: BLE001
            continue
        if any(_MODULO_JANELA in str(parte) for parte in cmdline):
            pids.add(int(proc.info["pid"]))
    return pids


class AcoesAtalho:
    """Executa a ação configurada; tudo local (127.0.0.1)."""

    def __init__(
        self,
        base_url: Callable[[], str] = _base_padrao,
        *,
        plataforma: str = sys.platform,
    ) -> None:
        self._base_url = base_url
        self._plataforma = plataforma
        self._filho: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def executar(self, acao: str) -> None:
        if acao == "app":
            self.abrir_app()
        else:
            self.abrir_flutuante()

    # -- mascote flutuante ---------------------------------------------------
    def _pids_mascote(self) -> set[int]:
        pids = _processos_do_mascote()
        filho = self._filho
        if filho is not None:
            if filho.poll() is None:
                pids.add(filho.pid)
            else:
                self._filho = None
        return pids

    def _focar_mascote(self) -> bool:
        """True se já existe uma janela do mascote (focada ou ainda abrindo)."""
        pids = self._pids_mascote()
        if not pids:
            return False
        if self._plataforma == "win32":
            from nicx.atalho import windows

            for hwnd, pid, _titulo in windows.listar_janelas():
                if pid in pids:
                    windows.focar(hwnd)
                    logger.info("Mascote já aberto: trazido para a frente")
                    return True
        logger.info("Mascote já está abrindo")
        return True

    def abrir_flutuante(self) -> None:
        from nicx.voz.escuta import runtime as rt

        with self._lock:
            if self._focar_mascote():
                return
            base = self._base_url()
            if not rt.window_supported():
                logger.info(
                    "Sem janela flutuante: abrindo a conversa por voz no navegador"
                )
                rt.open_in_browser(base)
                return
            if self._plataforma == "win32":
                from nicx.atalho import windows

                windows.permitir_foco_de_outros()
            self._filho = rt.spawn_mascot(base)
            logger.info("Abrindo o mascote pelo atalho (processo %s)", self._filho.pid)

    # -- app no navegador ----------------------------------------------------
    def _janela_do_app(self) -> Optional[int]:
        if self._plataforma != "win32":
            return None
        from nicx.atalho import windows

        mascote = self._pids_mascote()
        for hwnd, pid, titulo in windows.listar_janelas():
            if pid in mascote or not _TITULO_APP.match(titulo):
                continue
            nome = _nome_processo(pid)
            # O app de desktop do Nicx também conta; o Python (mascote), não.
            if nome in _NAVEGADORES or (
                nome.startswith("nicx") and not nome.startswith("python")
            ):
                return hwnd
        return None

    def abrir_app(self) -> None:
        with self._lock:
            hwnd = self._janela_do_app()
            if hwnd is not None:
                from nicx.atalho import windows

                # Mesmo se o Windows negar o foco (o botão pisca na barra de
                # tarefas), não abre uma segunda aba.
                windows.focar(hwnd)
                logger.info("App do Nicx já aberto: trazido para a frente")
                return
            base = self._base_url()
            logger.info("Abrindo o app do Nicx no navegador")
            webbrowser.open(f"{base}/")


__all__ = ["ACOES", "AcoesAtalho"]
