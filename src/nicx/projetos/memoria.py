"""Da conversa para o projeto: decisões e pendências ditas de passagem.

Roda junto com a memória automática (na thread dela, longe da resposta) e
só age com confiança alta:

- a mensagem cita um projeto que **já existe** pelo nome, depois da palavra
  "projeto" ("no projeto Lumen decidimos..."); nunca cria projeto;
- é uma afirmação (sem "?") e curta;
- tem um marcador claro: "decidimos/decidi/ficou decidido/we decided..."
  (decisão) ou "falta/preciso/tenho que/we need to/il faut..." (pendência).

No máximo uma anotação por mensagem, marcada com ``origem="auto"`` (a página
Projetos mostra como sugerida). Repetida não entra de novo. Sem modelo: é só
texto, então não custa tokens.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from nicx.projetos import busca
from nicx.projetos.armazenamento import Projetos

logger = logging.getLogger(__name__)

MAX_MENSAGEM = 400

_DECISAO = re.compile(
    r"\b(?:(?:n[oó]s|a gente)\s+)?(?:decidimos|decidi|ficou decidido|we(?:'ve| have)?"
    r" decided|i(?:'ve| have)? decided|hemos decidido|decidimos|on a d[ée]cid[ée]|"
    r"nous avons d[ée]cid[ée]|j'ai d[ée]cid[ée])\s+(?:que\s+|that\s+|to\s+|de\s+|d')?",
    re.IGNORECASE,
)
_PENDENCIA = re.compile(
    r"\b(?:ainda\s+)?(?:falta|faltam|preciso|precisamos|tenho que|temos que|"
    r"ficou pendente|(?:we|i)(?: still)? (?:need|have) to|still need to|"
    r"tengo que|tenemos que|hay que|il faut|je dois|nous devons|on doit)\s+",
    re.IGNORECASE,
)
_SENTENCAS = re.compile(r"[^.!;\n]+")


def _projeto_citado(mensagem: str, loja: Projetos):
    t = busca.normalizar(mensagem)
    candidatos = sorted(
        loja.listar(), key=lambda p: len(busca.normalizar(p.nome)), reverse=True
    )
    for projeto in candidatos:
        nome = busca.normalizar(projeto.nome)
        if not nome:
            continue
        if re.search(
            rf"\b(?:projeto|project|proyecto|projet)\s+(?:(?:do|da|de|the|el|le|du)\s+)?"
            rf"{re.escape(nome)}\b",
            t,
        ):
            return projeto
    return None


def _trecho(padrao: re.Pattern[str], mensagem: str) -> str:
    for sentenca in _SENTENCAS.findall(mensagem):
        m = padrao.search(sentenca)
        if m is None:
            continue
        corpo = sentenca[m.end() :].strip(" ,:-")
        if len(corpo.split()) >= 2:
            corpo = corpo[:200].rstrip()
            return corpo[:1].upper() + corpo[1:]
    return ""


def sugerir_da_conversa(
    mensagem: str, *, loja: Optional[Projetos] = None
) -> Optional[tuple[str, str, str]]:
    """Anota a decisão/pendência dita na *mensagem*; devolve (tipo, projeto, texto)."""
    mensagem = (mensagem or "").strip()
    if not mensagem or "?" in mensagem or len(mensagem) > MAX_MENSAGEM:
        return None
    from nicx.contexto.montagem import tem_contexto

    if tem_contexto(mensagem):
        return None
    loja = loja or Projetos()
    if not loja.caminho.exists():
        return None
    projeto = _projeto_citado(mensagem, loja)
    if projeto is None:
        return None
    decisao = _trecho(_DECISAO, mensagem)
    if decisao:
        alvo = busca.normalizar(decisao)
        if any(busca.normalizar(d.texto) == alvo for d in projeto.decisoes):
            return None
        loja.registrar_decisao(projeto.id, decisao, origem="auto")
        return ("decisao", projeto.nome, decisao)
    pendencia = _trecho(_PENDENCIA, mensagem)
    if pendencia:
        alvo = busca.normalizar(pendencia)
        if any(busca.normalizar(p.texto) == alvo for p in projeto.pendencias):
            return None
        loja.adicionar_pendencia(projeto.id, pendencia, origem="auto")
        return ("pendencia", projeto.nome, pendencia)
    return None


def sugerir_seguro(mensagem: str) -> None:
    """Para a memória automática: nunca levanta erro."""
    try:
        if sugerir_da_conversa(mensagem) is not None:
            logger.debug("Projeto: anotação sugerida pela conversa")
    except Exception:  # noqa: BLE001 — a memória nunca cai por causa disso
        logger.debug("Sugestão de projeto falhou", exc_info=True)


__all__ = ["sugerir_da_conversa", "sugerir_seguro"]
