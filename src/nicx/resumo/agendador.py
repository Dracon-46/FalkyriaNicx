"""Resumo do dia automático: notificação + voz no horário marcado.

Desligado por padrão (``[resumo] ativo = false``). Com o ``nicx serve``
aberto, o despertador dos lembretes confere a cada volta (10 s) se chegou a
hora: dia da semana marcado, já passou de ``hora`` e ainda não saiu hoje.
Se o servidor só ligar depois do horário, o resumo sai assim que ele subir
(no mesmo dia). A data do último envio fica em ``~/.nicx/resumo_estado.json``
para não repetir.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Dias da semana na ordem do ``datetime.weekday()``.
DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
_HORA = re.compile(r"^(?P<h>[01]?\d|2[0-3]):(?P<m>[0-5]\d)$")
_LOCK = threading.Lock()


def hora_de(valor: str) -> Optional[time]:
    """'18:00' -> time(18, 0); formato inválido -> None."""
    m = _HORA.match(str(valor or "").strip())
    if not m:
        return None
    return time(int(m.group("h")), int(m.group("m")))


def normalizar_dias(dias: Iterable[str]) -> List[str]:
    """Só os dias conhecidos, sem repetir, na ordem da semana."""
    pedidos = {str(d).strip().lower() for d in dias or []}
    return [d for d in DIAS if d in pedidos]


def config() -> Any:
    """``[resumo]`` da config carregada (o padrão, se não houver)."""
    try:
        from nicx.nucleo.config import load_config

        return load_config().resumo
    except Exception:  # noqa: BLE001
        from nicx.nucleo.config import ResumoConfig

        return ResumoConfig()


# ---------------------------------------------------------------------------
# Último envio
# ---------------------------------------------------------------------------


def _estado_path() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "resumo_estado.json"


def ultimo_envio() -> Optional[date]:
    path = _estado_path()
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
        return date.fromisoformat(str(dados.get("ultimo_envio", "")))
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def _marcar(dia: date) -> None:
    path = _estado_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"ultimo_envio": dia.isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Decidir e enviar
# ---------------------------------------------------------------------------


def deve_enviar(cfg: Any, agora: datetime, ultimo: Optional[date]) -> bool:
    """Ligado, dia marcado, já passou da hora e ainda não saiu hoje."""
    if not getattr(cfg, "ativo", False):
        return False
    hora = hora_de(getattr(cfg, "hora", ""))
    if hora is None:
        return False
    if DIAS[agora.weekday()] not in normalizar_dias(getattr(cfg, "dias", [])):
        return False
    if agora.time() < hora:
        return False
    return ultimo is None or ultimo < agora.date()


def idioma_padrao() -> str:
    """O idioma da voz (``[speech] language``), como código da interface."""
    from nicx.nucleo.idiomas import idioma

    try:
        from nicx.nucleo.config import load_config

        return idioma(getattr(load_config().speech, "language", "") or "").codigo
    except Exception:  # noqa: BLE001
        return idioma(None).codigo


def enviar(cfg: Any, agora: datetime, idioma: Optional[str] = None) -> str:
    """Monta o resumo de hoje, mostra a notificação e fala (conforme ``cfg``)."""
    from nicx.acoes import lembretes
    from nicx.nucleo.idiomas import PADRAO
    from nicx.nucleo.idiomas import idioma as _idioma
    from nicx.resumo.montagem import montar

    alvo = _idioma(idioma or idioma_padrao())
    texto = montar(agora.date(), alvo.codigo, agora=agora).texto
    if getattr(cfg, "notificar", True):
        lembretes.show_notification(texto)
    # Português: a voz escolhida pelo usuário. Outro idioma: a voz dele, se o
    # Kokoro falar (árabe não tem).
    if getattr(cfg, "falar", True) and (alvo.codigo == PADRAO or alvo.voz_kokoro):
        voz = "" if alvo.codigo == PADRAO else alvo.voz_kokoro
        lembretes.speak(texto, voice_id=voz)
    return texto


def verificar(
    agora: Optional[datetime] = None,
    cfg: Any = None,
    em_thread: bool = True,
) -> bool:
    """Envia o resumo se chegou a hora. Devolve True quando enviou."""
    cfg = cfg if cfg is not None else config()
    if not getattr(cfg, "ativo", False):
        return False
    if agora is None:
        from nicx.resumo.montagem import agora_local

        agora = agora_local()
    with _LOCK:
        if not deve_enviar(cfg, agora, ultimo_envio()):
            return False
        # Marca antes de falar: a fala demora e o despertador volta em 10 s.
        _marcar(agora.date())
    if em_thread:
        threading.Thread(
            target=_enviar_seguro, args=(cfg, agora), name="resumo-do-dia", daemon=True
        ).start()
    else:
        _enviar_seguro(cfg, agora)
    return True


def _enviar_seguro(cfg: Any, agora: datetime) -> None:
    try:
        enviar(cfg, agora)
    except Exception:  # noqa: BLE001 - o servidor continua
        logger.exception("Falha ao enviar o resumo do dia")


def ligar() -> None:
    """Pede ao despertador dos lembretes para conferir o horário do resumo."""
    from nicx.acoes import lembretes

    lembretes.add_task(verificar)


def desligar() -> None:
    from nicx.acoes import lembretes

    lembretes.remove_task(verificar)


__all__ = [
    "DIAS",
    "config",
    "desligar",
    "deve_enviar",
    "enviar",
    "hora_de",
    "ligar",
    "normalizar_dias",
    "ultimo_envio",
    "verificar",
]
