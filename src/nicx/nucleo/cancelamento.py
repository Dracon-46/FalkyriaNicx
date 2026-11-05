"""Parar uma resposta de verdade, não só a tela.

Antes, o botão Parar fechava a conexão do navegador, mas o agente seguia na
thread dele e o Ollama continuava gerando: num PC sem placa de vídeo, a
próxima pergunta esperava minutos atrás de uma resposta que ninguém ia ler.

A rota do chat cria um :class:`Cancelamento` por pedido e o põe em
:data:`ATUAL` antes de rodar o agente (``asyncio.to_thread`` copia o contexto,
então a thread vê o mesmo objeto). Quando o navegador desiste, a rota chama
:meth:`Cancelamento.cancelar`; o laço do agente confere :func:`verificar` entre
os passos e o motor do Ollama fecha a conexão no meio da geração (o Ollama
para quando o cliente some).
"""

from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Optional


class Cancelado(Exception):
    """A pessoa parou a resposta; não é erro do modelo."""


class Cancelamento:
    def __init__(self) -> None:
        self._evento = threading.Event()

    def cancelar(self) -> None:
        self._evento.set()

    @property
    def cancelado(self) -> bool:
        return self._evento.is_set()


ATUAL: ContextVar[Optional[Cancelamento]] = ContextVar(
    "nicx_cancelamento", default=None
)


def atual() -> Optional[Cancelamento]:
    return ATUAL.get()


def foi_cancelado() -> bool:
    pedido = ATUAL.get()
    return pedido is not None and pedido.cancelado


def verificar() -> None:
    """Levanta :class:`Cancelado` se a pessoa parou a resposta."""
    if foi_cancelado():
        raise Cancelado("resposta parada")


__all__ = ["ATUAL", "Cancelado", "Cancelamento", "atual", "foi_cancelado", "verificar"]
