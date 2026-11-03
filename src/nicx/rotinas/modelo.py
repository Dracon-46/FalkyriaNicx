"""Rotinas: um nome, as frases que a disparam, os passos e (se quiser) um horário.

Cada passo é uma ação rápida do Nicx (``nicx.acoes.intencoes.Action``). Só os
tipos de :data:`PASSOS_PERMITIDOS` entram: nada de desligar o PC, organizar
pastas ou apagar em lote dentro de uma rotina.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from nicx.acoes.intencoes import Action

DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
MAX_PASSOS = 20
MAX_FRASES = 5
MAX_NOME = 60
TIMER = "o tempo acabou"  # texto que nicx.acoes.lembretes reconhece como timer

PASSOS_PERMITIDOS = frozenset(
    {
        "volume",
        "media",
        "open",
        "open_url",
        "folder",
        "search",
        "youtube",
        "close",
        "note_add",
        "remind",
        "lock",
        "screenshot",
        "status",
        "time",
        "date",
        "battery",
        "resumo",
        "agenda_list",
        "remind_list",
    }
)


@dataclass
class Passo:
    """Uma ação da rotina.

    ``minutos`` vale para lembretes e timers, contados a partir da hora em que roda.
    """

    kind: str
    op: str = ""
    value: Optional[int] = None
    target: str = ""
    site: str = ""
    minutos: Optional[int] = None

    def para_acao(self, agora: Optional[datetime] = None) -> Action:
        when = None
        if self.kind == "remind":
            when = (agora or datetime.now()) + timedelta(minutes=self.minutos or 0)
        return Action(
            self.kind,
            op=self.op,
            value=self.value,
            target=self.target,
            site=self.site,
            when=when,
        )

    @classmethod
    def de_acao(cls, acao: Action, agora: Optional[datetime] = None) -> "Passo":
        minutos = None
        if acao.kind == "remind" and acao.when is not None:
            delta = acao.when - (agora or datetime.now())
            minutos = max(1, round(delta.total_seconds() / 60))
        return cls(acao.kind, acao.op, acao.value, acao.target, acao.site, minutos)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Passo":
        valor = dados.get("value")
        minutos = dados.get("minutos")
        return cls(
            kind=str(dados.get("kind", "")),
            op=str(dados.get("op", "") or ""),
            value=int(valor)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool)
            else None,
            target=str(dados.get("target", "") or "")[:300],
            site=str(dados.get("site", "") or "")[:40],
            minutos=int(minutos)
            if isinstance(minutos, (int, float)) and not isinstance(minutos, bool)
            else None,
        )


@dataclass
class Agenda:
    """Quando a rotina roda sozinha: dias da semana e hora local."""

    dias: list[str] = field(default_factory=list)
    hora: str = "08:00"

    @classmethod
    def de_dict(cls, dados: Optional[dict[str, Any]]) -> Optional["Agenda"]:
        if not dados:
            return None
        dias = [
            d
            for d in DIAS
            if d in {str(x).strip().lower() for x in dados.get("dias", [])}
        ]
        hora = str(dados.get("hora", "") or "")
        if not dias or not _hora_valida(hora):
            return None
        return cls(dias=dias, hora=hora)


def _hora_valida(hora: str) -> bool:
    try:
        datetime.strptime(hora, "%H:%M")
    except ValueError:
        return False
    return len(hora) == 5


@dataclass
class Rotina:
    nome: str
    passos: list[Passo]
    frases: list[str] = field(default_factory=list)
    agenda: Optional[Agenda] = None
    ativa: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    criada_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    ultima_execucao: str = ""
    ultimo_agendado: str = ""  # AAAA-MM-DD da última vez que rodou pelo horário
    idioma: str = ""

    def para_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["agenda"] = asdict(self.agenda) if self.agenda else None
        return dados

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Rotina":
        return cls(
            nome=str(dados.get("nome", "")).strip()[:MAX_NOME],
            passos=[
                Passo.de_dict(p) for p in dados.get("passos", []) if isinstance(p, dict)
            ][:MAX_PASSOS],
            frases=[
                str(f).strip()[:MAX_NOME]
                for f in dados.get("frases", [])
                if str(f).strip()
            ][:MAX_FRASES],
            agenda=Agenda.de_dict(dados.get("agenda")),
            ativa=bool(dados.get("ativa", True)),
            id=str(dados.get("id") or uuid.uuid4().hex[:10]),
            criada_em=str(
                dados.get("criada_em") or datetime.now().isoformat(timespec="seconds")
            ),
            ultima_execucao=str(dados.get("ultima_execucao", "") or ""),
            ultimo_agendado=str(dados.get("ultimo_agendado", "") or ""),
            idioma=str(dados.get("idioma", "") or ""),
        )


class RotinaInvalida(ValueError):
    """Nome vazio, passo não permitido ou rotina sem passos."""


def validar(rotina: Rotina) -> Rotina:
    if not rotina.nome:
        raise RotinaInvalida("nome vazio")
    if not rotina.passos:
        raise RotinaInvalida("sem passos")
    proibidos = sorted({p.kind for p in rotina.passos} - PASSOS_PERMITIDOS)
    if proibidos:
        raise RotinaInvalida(f"passos não permitidos: {', '.join(proibidos)}")
    for p in rotina.passos:
        if p.kind == "open_url" and not p.target.lower().startswith(
            ("http://", "https://")
        ):
            raise RotinaInvalida("endereço precisa começar com http:// ou https://")
        if p.kind == "remind" and not (p.minutos and 0 < p.minutos <= 24 * 60):
            raise RotinaInvalida("lembrete da rotina precisa de 1 a 1440 minutos")
    return rotina


__all__ = [
    "DIAS",
    "PASSOS_PERMITIDOS",
    "TIMER",
    "Agenda",
    "Passo",
    "Rotina",
    "RotinaInvalida",
    "validar",
]
