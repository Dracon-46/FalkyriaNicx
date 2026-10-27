"""Ações que pedem confirmação ("desliga o PC" -> "tem certeza?" -> "confirmo").

Guarda uma ação pendente por até 30 s. "Sim"/"confirmo" só viram comando
quando há algo pendente; fora disso seguem para o modelo como conversa.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from nicx.acoes.intencoes import Action

WINDOW_SECONDS = 30.0

_lock = threading.Lock()
_pending: Optional[tuple[Action, float]] = None


def ask(action: Action) -> None:
    global _pending
    with _lock:
        _pending = (action, time.monotonic())


def pending() -> Optional[Action]:
    with _lock:
        if _pending is None:
            return None
        action, since = _pending
        if time.monotonic() - since > WINDOW_SECONDS:
            return None
        return action


def take() -> Optional[Action]:
    """Devolve e esquece a ação pendente (se ainda estiver no prazo)."""
    global _pending
    action = pending()
    with _lock:
        _pending = None
    return action


def drop() -> bool:
    global _pending
    had = pending() is not None
    with _lock:
        _pending = None
    return had
