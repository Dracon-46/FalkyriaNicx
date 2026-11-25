"""A busca: cada fonte devolve resultados com a mesma cara.

Casamento sem acento e sem maiúscula; todas as palavras da busca precisam
aparecer (em qualquer ordem). Fonte que falha é pulada: a busca nunca cai por
causa de um arquivo estragado.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

MAX_POR_FONTE = 20
TRECHO = 180


@dataclass
class Achado:
    fonte: str
    titulo: str
    trecho: str = ""
    quando: str = ""
    link: str = ""
    ref: str = ""
    pontos: float = 0.0
    extra: dict = field(default_factory=dict)


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def palavras(busca: str) -> list[str]:
    return [p for p in re.findall(r"\w+", normalizar(busca)) if len(p) >= 2]


def casa(texto: str, termos: list[str]) -> float:
    """0 se falta alguma palavra; senão, quantas vezes elas aparecem."""
    t = normalizar(texto)
    total = 0
    for termo in termos:
        n = t.count(termo)
        if not n:
            return 0
        total += n
    return float(total)


def trecho(texto: str, termos: list[str], tamanho: int = TRECHO) -> str:
    """Pedaço do texto em volta da primeira palavra achada."""
    limpo = " ".join((texto or "").split())
    if len(limpo) <= tamanho:
        return limpo
    t = normalizar(limpo)
    pos = min((i for i in (t.find(x) for x in termos) if i >= 0), default=0)
    inicio = max(0, pos - tamanho // 3)
    fim = min(len(limpo), inicio + tamanho)
    return (
        ("…" if inicio else "")
        + limpo[inicio:fim].strip()
        + ("…" if fim < len(limpo) else "")
    )


# ------------------------------------------------------------------ fontes


def _projetos(termos: list[str]) -> Iterable[Achado]:
    from nicx.projetos.armazenamento import Projetos

    for p in Projetos().listar(arquivados=True):
        partes = [
            p.nome,
            p.objetivo,
            p.estado,
            *(d.texto for d in p.decisoes),
            *(x.texto for x in p.pendencias),
            *p.proximos_passos,
        ]
        texto = "\n".join(x for x in partes if x)
        pontos = casa(texto, termos) + 2 * casa(p.nome, termos)
        if pontos:
            yield Achado(
                "projeto",
                p.nome,
                trecho(texto, termos),
                p.ultima_atividade,
                "/projetos",
                p.id,
                pontos,
                {"arquivado": p.arquivado},
            )


def _notas(termos: list[str]) -> Iterable[Achado]:
    from nicx.acoes import notas

    for i, nota in enumerate(notas.all_notes()):
        pontos = casa(nota, termos)
        if pontos:
            yield Achado("nota", trecho(nota, termos, 120), "", "", "", str(i), pontos)


def _lembretes(termos: list[str]) -> Iterable[Achado]:
    from nicx.acoes import lembretes

    for r in lembretes.pending():
        pontos = casa(r.text, termos)
        if pontos:
            yield Achado("lembrete", r.text, "", r.due, "", r.id, pontos)


def _agenda(termos: list[str]) -> Iterable[Achado]:
    from nicx.acoes import agenda

    for e in agenda._load():
        texto = "\n".join(x for x in (e.title, e.location, e.details) if x)
        pontos = casa(texto, termos)
        if pontos:
            yield Achado(
                "compromisso",
                e.title,
                trecho("\n".join(x for x in (e.location, e.details) if x), termos),
                e.start,
                "",
                e.id,
                pontos,
            )


def _memoria(termos: list[str]) -> Iterable[Achado]:
    from datetime import datetime, timezone

    from nicx.memoria.store import LocalFactStore

    for i, f in enumerate(LocalFactStore().list()):
        if not f.trusted_for_recall:
            continue
        pontos = casa(f.text, termos)
        if pontos:
            quando = (
                datetime.fromtimestamp(f.created_at, tz=timezone.utc).isoformat(
                    timespec="seconds"
                )
                if f.created_at
                else ""
            )
            yield Achado(
                "memoria", trecho(f.text, termos), "", quando, "", str(i), pontos
            )


def _historico(termos: list[str], busca: str) -> Iterable[Achado]:
    from nicx.historico.registro import registro

    for a in registro().listar(busca=busca, limite=MAX_POR_FONTE):
        yield Achado(
            "historico",
            a.titulo,
            "",
            a.quando,
            "/historico",
            str(a.id),
            1 + casa(a.titulo, termos),
            {"tipo": a.tipo},
        )


def _trabalho(termos: list[str]) -> Iterable[Achado]:
    from nicx.trabalho import servico

    for t in servico.listar():
        texto = "\n".join(
            x
            for x in (t.get("pedido", ""), t.get("resumo", ""), t.get("pasta", ""))
            if x
        )
        pontos = casa(texto, termos)
        if pontos:
            yield Achado(
                "trabalho",
                t.get("pedido", ""),
                trecho(t.get("resumo", "") or t.get("pasta", ""), termos),
                t.get("atualizado_em", ""),
                "/trabalho",
                str(t.get("id", "")),
                pontos,
                {"estado": t.get("estado", "")},
            )


FONTES: dict[str, Callable[..., Iterable[Achado]]] = {
    "projeto": _projetos,
    "nota": _notas,
    "lembrete": _lembretes,
    "compromisso": _agenda,
    "memoria": _memoria,
    "trabalho": _trabalho,
}


def buscar(busca: str, fontes: Optional[list[str]] = None) -> dict[str, Any]:
    """Resultados por fonte (melhores primeiro), mais as fontes que falharam."""
    termos = palavras(busca)
    resultado: dict[str, Any] = {"busca": busca, "resultados": [], "falharam": []}
    if not termos:
        return resultado
    escolhidas = fontes or [*FONTES, "historico"]
    for nome in escolhidas:
        try:
            if nome == "historico":
                achados = list(_historico(termos, busca))
            elif nome in FONTES:
                achados = list(FONTES[nome](termos))
            else:
                continue
        except Exception:  # noqa: BLE001 - uma fonte estragada não derruba a busca
            logger.debug("Busca: a fonte %s falhou", nome, exc_info=True)
            resultado["falharam"].append(nome)
            continue
        achados.sort(key=lambda a: (a.pontos, a.quando), reverse=True)
        resultado["resultados"].extend(asdict(a) for a in achados[:MAX_POR_FONTE])
    return resultado


__all__ = ["Achado", "buscar", "casa", "normalizar", "palavras", "trecho"]
