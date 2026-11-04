# ruff: noqa: E501  (tabela de padrões: um por linha fica mais legível)
"""Frases dos assistentes: usar, voltar para o Nicx, listar, qual está ativo e criar.

As quatro primeiras são ações rápidas (``Action("assistente", op)``) e chegam
aqui pelo texto já limpo (minúsculas, sem acento nem gentilezas). Usar exige a
palavra "assistente", a não ser que o nome seja de um assistente que existe:
"fala com o Professor" só vira pedido se houver um assistente "Professor".

Criar ("cria um assistente que revisa contratos") precisa do modelo, então é
a rota do chat que chama :func:`criacao`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from nicx.acoes.intencoes import Action, original_text

KIND = "assistente"

_USAR = (
    r"^(?:fala|falar|quero falar|conversa|conversar|usa|use|usar|chama|chame|ativa|ative|abre|abra|liga|ligue|troca|troque|muda|mude)"
    r"(?:\s+(?:com|para|pra|pro))?\s+(?:o|a|meu|minha)?\s*(?:assistente|ajudante)\s+(?:de\s+|do\s+|da\s+)?(?P<nome>.+)$",
    r"^(?:talk|speak|chat|switch)\s+(?:to|with)\s+(?:the\s+|my\s+)?(?P<nome>.+?)\s+assistant$",
    r"^(?:talk|speak|chat|switch)\s+(?:to|with)\s+(?:the\s+|my\s+)?assistant\s+(?P<nome>.+)$",
    r"^(?:use|open|start)\s+(?:the\s+|my\s+)?(?P<nome>.+?)\s+assistant$",
    r"^(?:habla|hablar|usa|usar|activa|abre|cambia)\s+(?:con\s+|a\s+)?(?:el|mi)\s+asistente\s+(?:de\s+)?(?P<nome>.+)$",
    r"^(?:parle|parler|utilise|active|ouvre|passe)\s+(?:a|avec)?\s*(?:l\s+|mon\s+)?assistant\s+(?P<nome>.+)$",
)
# Sem a palavra "assistente": só se o nome existir.
_USAR_PELO_NOME = (
    r"^(?:fala|falar|quero falar|conversa|conversar)\s+com\s+(?:o|a)\s+(?P<nome>.+)$",
    r"^(?:talk|speak)\s+to\s+(?:the\s+)?(?P<nome>.+)$",
    r"^habla\s+con\s+(?:el|la)\s+(?P<nome>.+)$",
    r"^parle\s+(?:a|au|avec)\s+(?:l\s+|la\s+|le\s+)?(?P<nome>.+)$",
)
# A limpeza das ações rápidas tira a palavra "Nicx" (é a de chamada): "volta
# pro Nicx" chega aqui como "volta pro".
_SAIR = (
    r"^(?:volta|volte|voltar)\s+(?:pro|para o|pra o|ao|a ser o)(?:\s+nicx)?(?:\s+normal)?$",
    r"^(?:volta|volte|voltar)\s+ao\s+normal$",
    r"^(?:sai|saia|sair|fecha|feche|desativa|desative|desliga|desligue|encerra|encerre)\s+(?:do|o|a|da)\s+(?:assistente|ajudante)$",
    r"^(?:go\s+)?back\s+to(?:\s+nicx)?$",
    r"^(?:stop|exit|close|quit|leave|turn off)\s+the\s+assistant$",
    r"^(?:vuelve|volver|regresa)\s+a(?:\s+nicx)?$",
    r"^(?:sal|salir|cierra|desactiva)\s+(?:del|el)\s+asistente$",
    r"^(?:reviens|revenir|retourne)\s+(?:a|vers)(?:\s+nicx)?$",
    r"^(?:quitte|ferme|desactive)\s+l\s+assistant$",
)
_LISTAR = (
    r"^(?:quais|que)\s+(?:sao\s+)?(?:os\s+)?(?:meus\s+)?assistentes\s*(?:eu\s+)?(?:tenho|existem|tem)?$",
    r"^(?:lista|liste|mostra|mostre)\s+(?:os\s+|meus\s+|os meus\s+)?assistentes$",
    r"^meus assistentes$",
    r"^(?:list|show)\s+(?:my|the)\s+assistants$",
    r"^(?:which|what)\s+assistants\s+do\s+i\s+have$",
    r"^(?:cuales|que)\s+asistentes\s+tengo$",
    r"^(?:lista|muestra)\s+(?:mis|los)\s+asistentes$",
    r"^(?:liste|montre)\s+(?:mes|les)\s+assistants$",
    r"^quels\s+assistants\s+(?:j\s+ai|ai je)$",
)
_QUAL = (
    r"^(?:qual|que)\s+assistente\s+(?:esta|ta|e o que esta)\s+(?:ativo|ligado|falando)$",
    r"^(?:qual|que)\s+(?:e\s+)?o\s+assistente\s+(?:ativo|atual)$",
    r"^(?:which|what)\s+assistant\s+is\s+(?:active|on|talking)$",
    r"^que\s+asistente\s+esta\s+activo$",
    r"^quel\s+assistant\s+est\s+actif$",
)
_CRIAR = (
    r"^(?:cria|crie|criar|monta|monte|montar|faz|faca|fazer)\s+(?:um|uma|o|meu)\s+(?:novo\s+)?(?:assistente|ajudante)\s+(?P<desc>.+)$",
    r"^(?:quero|preciso de)\s+um\s+(?:novo\s+)?assistente\s+(?P<desc>(?:que|para|pra|de)\s+.+)$",
    r"^(?:create|make|build|set up)\s+(?:me\s+)?(?:an?|my)\s+(?:new\s+)?assistant\s+(?P<desc>.+)$",
    r"^(?:crea|crear|haz|arma)\s+(?:me\s+)?un\s+(?:nuevo\s+)?asistente\s+(?P<desc>.+)$",
    r"^(?:cree|creer|fais|fabrique)\s+(?:moi\s+)?un\s+(?:nouvel\s+)?assistant\s+(?P<desc>.+)$",
)


def _compilar(padroes: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in padroes)


_R_USAR = _compilar(_USAR)
_R_USAR_PELO_NOME = _compilar(_USAR_PELO_NOME)
_R_SAIR = _compilar(_SAIR)
_R_LISTAR = _compilar(_LISTAR)
_R_QUAL = _compilar(_QUAL)
_R_CRIAR = _compilar(_CRIAR)


def _achar(regras: tuple[re.Pattern[str], ...], t: str) -> Optional[re.Match[str]]:
    for regra in regras:
        achado = regra.match(t)
        if achado is not None:
            return achado
    return None


def parse(text: str, t: str, where: list[int]) -> Optional[Action]:
    """O pedido em *t* (texto limpo de *text*), ou None.

    ``Action("assistente", op, target=nome)``: *op* é usar, sair, listar ou qual.
    """
    if not t:
        return None
    if _achar(_R_SAIR, t):
        return Action(KIND, "sair")
    if _achar(_R_LISTAR, t):
        return Action(KIND, "listar")
    if _achar(_R_QUAL, t):
        return Action(KIND, "qual")
    achado = _achar(_R_USAR, t)
    if achado is not None:
        inicio, fim = achado.span("nome")
        return Action(KIND, "usar", target=original_text(text, where, inicio, fim))
    achado = _achar(_R_USAR_PELO_NOME, t)
    if achado is not None:
        from nicx.assistentes import armazenamento

        inicio, fim = achado.span("nome")
        nome = original_text(text, where, inicio, fim)
        existente = armazenamento.por_nome(nome)
        if existente is not None:
            return Action(KIND, "usar", target=existente.nome)
    return None


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(
        r"^(?:(?:ei|oi|ok|hey)\s+)?(?:nicx|nix)?\s*(?:por favor|please)?\s*",
        "",
        " ".join(texto.split()),
    )
    return texto.strip()


def criacao(texto: str) -> Optional[str]:
    """A descrição em "cria um assistente que revisa contratos", ou None."""
    t = _normalizar(texto)
    if not t or len(t) > 500:
        return None
    achado = _achar(_R_CRIAR, t)
    if achado is None:
        return None
    descricao = achado.group("desc").strip()
    if len(descricao.split()) < 2:
        return None  # "cria um assistente novo": a tela ou o modelo resolvem
    palavras = texto.split()
    # A descrição com as letras do usuário: as últimas N palavras do original.
    n = len(descricao.split())
    original = " ".join(palavras[-n:]) if len(palavras) >= n else descricao
    return original.strip(" .!?")


__all__ = ["KIND", "criacao", "parse"]
