"""O assistente desta conversa: instruções no prompt e ferramentas permitidas.

A rota do chat põe o assistente ativo em :data:`ATUAL` no começo do pedido; o
``SystemPromptBuilder`` acrescenta :func:`secao` e o ``ToolExecutor`` só
mostra e só executa as ferramentas que ele permite. Fora do chat (agentes
agendados, CLI) não há assistente e nada muda.
"""

from __future__ import annotations

import contextvars
from typing import Any, Callable, Iterable, Optional, TypeVar

from nicx.assistentes.modelo import Assistente

ATUAL: contextvars.ContextVar[Optional[Assistente]] = contextvars.ContextVar(
    "nicx_assistente", default=None
)
_T = TypeVar("_T")


def secao(assistente: Optional[Assistente] = None) -> str:
    a = assistente if assistente is not None else ATUAL.get()
    if a is None:
        return ""
    return (
        f"## Assistente: {a.nome}\n\n"
        f'Nesta conversa você atua como "{a.nome}", um assistente que o usuário '
        "montou no Nicx. Siga as instruções dele abaixo sem deixar de lado as "
        "regras acima.\n\n"
        f"{a.instrucoes}"
    )


def com_assistente(prompt: str) -> str:
    """*prompt* com a seção do assistente no fim (o começo continua igual)."""
    extra = secao()
    if not extra:
        return prompt
    return f"{prompt}\n\n{extra}" if prompt else extra


def permite(ferramenta: str) -> bool:
    a = ATUAL.get()
    return a is None or a.permite(ferramenta)


def filtrar(
    ferramentas: Iterable[_T], nome: Optional[Callable[[_T], str]] = None
) -> list[_T]:
    """As ferramentas que o assistente atual pode usar (todas, sem assistente)."""
    if ATUAL.get() is None:
        return list(ferramentas)
    pegar: Callable[[Any], str] = nome or (lambda t: t.spec.name)
    return [t for t in ferramentas if permite(pegar(t))]


def usa_memoria() -> bool:
    a = ATUAL.get()
    return a is None or a.memoria


__all__ = ["ATUAL", "com_assistente", "filtrar", "permite", "secao", "usa_memoria"]
