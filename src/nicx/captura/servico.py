"""Captura rápida para as notas.

Aperta o atalho ``[captura]`` em qualquer programa: o Nicx espera as teclas
serem soltas, copia o que está selecionado (devolvendo à área de transferência
o que havia antes) e, se não houver seleção, usa o texto já copiado. O texto
vai para ``notas.md`` com o nome do programa de onde veio, e um aviso do
Windows confirma. Janela sensível (senhas, bancos) nunca é capturada, e o
texto não vai para os logs.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_CARACTERES = 1500

OK = "ok"
VAZIO = "vazio"
SENSIVEL = "sensivel"
SEM_SUPORTE = "sem_suporte"


@dataclass
class Captura:
    motivo: str
    texto: str = ""
    origem: str = ""


def _esperar_soltar(limite_s: float = 1.5) -> None:
    """Espera Ctrl/Alt/Shift/Win soltos (senão o Ctrl+C sai errado)."""
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if not any(
            user32.GetAsyncKeyState(t) & 0x8000 for t in (0x10, 0x11, 0x12, 0x5B, 0x5C)
        ):
            return
        time.sleep(0.03)


def _janela():
    try:
        from nicx.contexto import janela

        return janela.em_primeiro_plano()
    except Exception:  # noqa: BLE001
        return None


def _selecao() -> str:
    try:
        from nicx.contexto import selecao

        return selecao.copiar_selecao(MAX_CARACTERES * 2)
    except Exception:  # noqa: BLE001
        logger.debug("Captura: não deu para copiar a seleção", exc_info=True)
        return ""


def _copiado() -> str:
    try:
        from nicx.contexto import area_transferencia

        return area_transferencia.ler(MAX_CARACTERES * 2).texto or ""
    except Exception:  # noqa: BLE001
        return ""


def linha_da_nota(texto: str, origem: str = "") -> str:
    """Uma linha só (as notas são uma por linha), cortada, com a origem."""
    limpo = " ".join(texto.split())
    if len(limpo) > MAX_CARACTERES:
        limpo = limpo[: MAX_CARACTERES - 1].rstrip() + "…"
    return f"{limpo} (de {origem})" if origem else limpo


def capturar(
    *,
    janela: Callable[[], object] = _janela,
    selecao: Callable[[], str] = _selecao,
    copiado: Callable[[], str] = _copiado,
    esperar: Callable[[], None] = _esperar_soltar,
    guardar: Optional[Callable[[str], None]] = None,
    avisar: Optional[Callable[[str], None]] = None,
) -> Captura:
    """Faz a captura; os parâmetros existem para os testes."""
    from nicx.contexto import janela as jn

    if guardar is None:
        from nicx.acoes import notas

        guardar = notas.add
    if avisar is None:
        from nicx.acoes.lembretes import show_notification

        avisar = show_notification

    info = janela()
    if info is not None and jn.sensivel(info):
        avisar("Captura rápida: essa janela é protegida; nada foi guardado.")
        return Captura(SENSIVEL)
    esperar()
    texto = (selecao() or "").strip() or (copiado() or "").strip()
    if not texto:
        avisar("Captura rápida: selecione ou copie um texto e aperte o atalho de novo.")
        return Captura(VAZIO)
    origem = ""
    if info is not None and not jn.do_nicx(info) and not jn.do_sistema(info):
        origem = jn.nome_app(info)
    linha = linha_da_nota(texto, origem)
    guardar(linha)
    previa = linha if len(linha) <= 80 else linha[:79] + "…"
    avisar(f"Guardado nas notas: {previa}")
    return Captura(OK, linha, origem)


class AcoesCaptura:
    """O que o atalho da captura faz (mesma interface do atalho do Nicx)."""

    def __init__(self, fazer: Callable[[], object] = capturar) -> None:
        self._fazer = fazer
        self._ocupado = threading.Lock()

    def executar(self, _acao: str = "") -> None:
        # Fora da thread do atalho, uma captura por vez.
        def rodar() -> None:
            if not self._ocupado.acquire(blocking=False):
                return
            try:
                self._fazer()
            except Exception:  # noqa: BLE001
                logger.warning("A captura rápida falhou", exc_info=True)
            finally:
                self._ocupado.release()

        threading.Thread(target=rodar, name="nicx-captura", daemon=True).start()


def _escuta_captura(combinacao, ao_apertar):
    from nicx.atalho.windows import HOTKEY_ID_CAPTURA, EscutaAtalho, laco_compartilhado

    return EscutaAtalho(
        combinacao, ao_apertar, ident=HOTKEY_ID_CAPTURA, laco=laco_compartilhado()
    )


def gerenciador():
    """Um GerenciadorAtalho com a ação de captura e o id próprio."""
    from nicx.atalho.servico import GerenciadorAtalho

    return GerenciadorAtalho(AcoesCaptura(), fabrica_escuta=_escuta_captura)


__all__ = [
    "AcoesCaptura",
    "Captura",
    "OK",
    "SENSIVEL",
    "VAZIO",
    "capturar",
    "gerenciador",
    "linha_da_nota",
]
