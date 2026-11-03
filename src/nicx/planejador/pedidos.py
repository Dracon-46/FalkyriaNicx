# ruff: noqa: E501  (tabelas de padrões: um por linha fica mais legível)
"""'monta um plano para aprender inglês até dezembro', 'make a plan to run 10 km by june'.

Só vira pedido se o prazo for entendido (senão segue para o modelo como conversa).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Optional

from nicx.planejador.prazo import interpretar as interpretar_prazo

_PADROES = {
    "pt-BR": [
        r"(?:monta|monte|cria|crie|faz|faca|planeja|planeje)(?: um| o| meu)? plano (?:para|pra|de) (?P<obj>.+?) (?P<prazo>(?:ate|em|daqui a|dentro de) .+)",
        r"(?:quero|preciso|vou) (?P<obj>.+?) (?P<prazo>ate .+)",
    ],
    "en": [
        r"(?:make|create|build|plan)(?: me)?(?: a| my)? plan (?:to|for) (?P<obj>.+?) (?P<prazo>(?:by|until|in|within|before) .+)",
        r"(?:i want|i need|i m going) to (?P<obj>.+?) (?P<prazo>(?:by|until|before) .+)",
    ],
    "es": [
        r"(?:haz|crea|arma|planea)(?: me)?(?: un| mi)? plan para (?P<obj>.+?) (?P<prazo>(?:hasta|en|antes de|dentro de) .+)",
        r"(?:quiero|necesito) (?P<obj>.+?) (?P<prazo>(?:hasta|antes de) .+)",
    ],
    "fr": [
        r"(?:fais|cree|prepare)(?: moi)?(?: un| mon)? plan pour (?P<obj>.+?) (?P<prazo>(?:d ici|avant|dans|en) .+)",
        r"(?:je veux|je dois) (?P<obj>.+?) (?P<prazo>(?:d ici|avant) .+)",
    ],
}


@dataclass
class PedidoPlano:
    objetivo: str
    prazo: date


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s/]", " ", texto)
    texto = re.sub(
        r"^(?:(?:ei|oi|ok|hey)\s+)?(?:nicx|nix)?\s*(?:por favor|please)?\s*",
        "",
        " ".join(texto.split()),
    )
    return texto.strip()


def detectar(
    texto: str, codigo: str = "pt-BR", hoje: Optional[date] = None
) -> Optional[PedidoPlano]:
    t = _normalizar(texto)
    if not t or len(t) > 300:
        return None
    codigos = ["pt-BR"] if codigo == "pt-BR" else [codigo, "pt-BR"]
    for cod in codigos:
        for padrao in _PADROES.get(cod, []):
            m = re.fullmatch(padrao, t)
            if not m:
                continue
            prazo = interpretar_prazo(m.group("prazo"), hoje)
            if prazo is None:
                continue
            objetivo = _objetivo_original(texto, m.group("obj"))
            return PedidoPlano(objetivo=objetivo, prazo=prazo)
    return None


def _objetivo_original(texto: str, obj_norm: str) -> str:
    """O objetivo com as letras do usuário (acentos, maiúsculas), quando dá para achar."""
    palavras = obj_norm.split()
    if not palavras:
        return obj_norm
    originais = texto.split()
    norm = [_normalizar(p) for p in originais]
    for i in range(len(norm)):
        if norm[i : i + len(palavras)] == palavras:
            return " ".join(originais[i : i + len(palavras)])
    return obj_norm


__all__ = ["PedidoPlano", "detectar"]
