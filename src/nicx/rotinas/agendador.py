"""Rotinas com horário: rodam sozinhas com o ``nicx serve`` ligado.

No dia marcado, a partir da hora, uma vez por dia. Se o servidor só subir
depois, a rotina ainda roda se não tiver passado :data:`JANELA` da hora (abrir
apps às 15h para a aula das 9h não ajuda). Usa o despertador dos lembretes
(``lembretes.add_task``), que confere a cada 10 s.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from nicx.rotinas import armazenamento, textos
from nicx.rotinas.modelo import DIAS, Rotina

logger = logging.getLogger(__name__)
JANELA = timedelta(hours=2)
_LOCK = threading.Lock()


def deve_rodar(rotina: Rotina, agora: datetime) -> bool:
    if not rotina.ativa or rotina.agenda is None:
        return False
    if DIAS[agora.weekday()] not in rotina.agenda.dias:
        return False
    hora, minuto = (int(x) for x in rotina.agenda.hora.split(":"))
    inicio = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if not (inicio <= agora < inicio + JANELA):
        return False
    return rotina.ultimo_agendado != agora.date().isoformat()


def _rodar(rotina: Rotina) -> None:
    from nicx.acoes import lembretes
    from nicx.rotinas.servico import executar

    try:
        _ok, frase = executar(rotina, origem="rotina", idioma=rotina.idioma or None)
        lembretes.show_notification(frase)
    except Exception:  # noqa: BLE001 - o despertador não pode morrer
        logger.exception("Rotina %s falhou", rotina.nome)


def verificar(agora: Optional[datetime] = None) -> list[str]:
    """Roda as rotinas que chegaram na hora. Devolve os ids disparados."""
    agora = agora or datetime.now()
    disparadas = []
    with _LOCK:
        for rotina in armazenamento.listar():
            if not deve_rodar(rotina, agora):
                continue
            # marca antes de rodar: um servidor reiniciado não roda duas vezes
            armazenamento.marcar(rotina.id, ultimo_agendado=agora.date().isoformat())
            disparadas.append(rotina.id)
            threading.Thread(
                target=_rodar, args=(rotina,), name=f"rotina-{rotina.id}", daemon=True
            ).start()
    return disparadas


def _tarefa() -> None:
    try:
        verificar()
    except Exception:  # noqa: BLE001
        logger.exception("Agendador de rotinas falhou")


def ligar() -> None:
    from nicx.acoes import lembretes

    lembretes.add_task(_tarefa)


def desligar() -> None:
    from nicx.acoes import lembretes

    lembretes.remove_task(_tarefa)


__all__ = ["JANELA", "deve_rodar", "desligar", "ligar", "textos", "verificar"]
