"""Ações que pedem confirmação ("desliga o PC" -> "tem certeza?" -> "confirmo").

Guarda uma ação pendente por até 30 s. "Sim"/"confirmo" só viram comando
quando há algo pendente; fora disso seguem para o modelo como conversa.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from nicx.acoes.intencoes import Action

WINDOW_SECONDS = 30.0
# ferramenta do modelo esperando "confirmo": dá tempo de ler a resposta
TOOL_WINDOW_SECONDS = 120.0

_lock = threading.Lock()
_pending: Optional[tuple[Action, float, float, Optional[Callable[[], str]]]] = None


def ask(
    action: Action,
    window: float = WINDOW_SECONDS,
    fn: Optional[Callable[[], str]] = None,
) -> None:
    """Guarda a ação; com ``fn``, "confirmo" roda ``fn`` (que devolve a frase)."""
    global _pending
    with _lock:
        _pending = (action, time.monotonic(), window, fn)


def pending() -> Optional[Action]:
    with _lock:
        if _pending is None:
            return None
        action, since, window, _fn = _pending
        if time.monotonic() - since > window:
            return None
        return action


def take_all() -> tuple[Optional[Action], Optional[Callable[[], str]]]:
    """Devolve e esquece a ação pendente e a função dela (se ainda no prazo)."""
    global _pending
    action = pending()
    with _lock:
        fn = _pending[3] if (_pending is not None and action is not None) else None
        _pending = None
    return action, fn


def take() -> Optional[Action]:
    """Devolve e esquece a ação pendente (se ainda estiver no prazo)."""
    return take_all()[0]


def drop() -> bool:
    global _pending
    had = pending() is not None
    with _lock:
        _pending = None
    return had
