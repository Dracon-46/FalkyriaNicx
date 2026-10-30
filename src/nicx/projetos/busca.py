"""Achar um projeto pelo nome dito ou digitado, com tolerância.

"nicx site", "Nicx-Site", "o site" e "NicxSite" acham "Nicx Site": sem
acento, sem maiúsculas, sem pontuação, parcial. Na dúvida entre dois, o
de atividade mais recente.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from nicx.projetos.modelo import Projeto

# Palavras que não fazem parte do nome ("o projeto do Lumen").
_VAZIAS = frozenset(
    {
        "o", "a", "os", "as", "do", "da", "de", "dos", "das", "meu", "minha",
        "projeto", "project", "proyecto", "projet", "the", "my", "el", "la",
        "mi", "le", "mon", "ma", "du", "des", "of",
    }
)  # fmt: skip


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento nem pontuação, espaços simples."""
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]|_", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _palavras(texto: str) -> list[str]:
    return [p for p in normalizar(texto).split() if p not in _VAZIAS]


def pontuar(consulta: str, nome: str) -> int:
    """De 0 (nada a ver) a 100 (mesmo nome)."""
    q, n = normalizar(consulta), normalizar(nome)
    if not q or not n:
        return 0
    if q == n:
        return 100
    q_junto, n_junto = q.replace(" ", ""), n.replace(" ", "")
    if q_junto == n_junto:
        return 95
    qp, np_ = _palavras(consulta), _palavras(nome)
    if qp and qp == np_:
        return 90
    if len(q_junto) >= 2 and n_junto.startswith(q_junto):
        return 80
    if qp and all(any(w.startswith(p) for w in np_) for p in qp):
        return 70
    if len(q_junto) >= 3 and q_junto in n_junto:
        return 60
    # O nome inteiro dentro do que foi dito ("o projeto lumen novo").
    if len(n_junto) >= 3 and re.search(rf"\b{re.escape(n)}\b", q):
        return 50
    return 0


def buscar(
    consulta: str, projetos: Iterable[Projeto], minimo: int = 50
) -> list[Projeto]:
    """Os projetos que combinam com *consulta*, do melhor para o pior."""
    achados = []
    for projeto in projetos:
        nota = pontuar(consulta, projeto.nome)
        if nota >= minimo:
            achados.append((nota, projeto.ultima_atividade, projeto))
    achados.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [projeto for _, _, projeto in achados]


def melhor(consulta: str, projetos: Iterable[Projeto]) -> Optional[Projeto]:
    achados = buscar(consulta, projetos)
    return achados[0] if achados else None


def nome_no_comeco(texto: str, projetos: Iterable[Projeto]) -> Optional[Projeto]:
    """O projeto cujo nome abre *texto* ("lumen comprar domínio" -> Lumen).

    Para frases sem dois-pontos em que o nome e o resto vêm grudados.
    O nome mais longo ganha ("Nicx Site" antes de "Nicx").
    """
    t = normalizar(texto)
    candidatos = sorted(projetos, key=lambda p: len(normalizar(p.nome)), reverse=True)
    for projeto in candidatos:
        n = normalizar(projeto.nome)
        if n and (t == n or t.startswith(n + " ")):
            return projeto
    return None


__all__ = ["buscar", "melhor", "nome_no_comeco", "normalizar", "pontuar"]
