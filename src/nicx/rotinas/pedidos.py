# ruff: noqa: E501  (tabelas de padrões: um por linha fica mais legível)
"""Frases das rotinas: criar, listar, apagar e rodar (pt, en, es, fr).

"cria a rotina preparar faculdade: abre o chrome, abre o vs code, volume 30,
timer de 50 minutos, toda segunda às 9h". Também rodam pela frase exata do
nome (ou de uma das frases da rotina): "preparar faculdade".

O texto é normalizado sem mudar o tamanho (cada caractere vira um), assim o
trecho dos passos sai do texto original, com maiúsculas e acentos.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from nicx.acoes.intencoes import Action

_CRIAR = {
    "pt-BR": r"(?:cria|crie|criar|cadastra|cadastre|monta|monte|nova)(?: uma| a)?(?: nova)? rotina(?: chamada| de nome| com o nome)? (?P<nome>[^:]+?)\s*:\s*(?P<resto>.*)",
    "en": r"(?:create|make|add|set up|new)(?: a| the)?(?: new)? routine(?: called| named)? (?P<nome>[^:]+?)\s*:\s*(?P<resto>.*)",
    "es": r"(?:crea|crear|haz|nueva)(?: una| la)?(?: nueva)? rutina(?: llamada)? (?P<nome>[^:]+?)\s*:\s*(?P<resto>.*)",
    "fr": r"(?:cree|creer|fais|nouvelle)(?: une| la)?(?: nouvelle)? routine(?: appelee| nommee)? (?P<nome>[^:]+?)\s*:\s*(?P<resto>.*)",
}
_LISTAR = {
    "pt-BR": r"(?:quais (?:sao )?)?(?:as )?minhas rotinas|lista(?:r)? (?:as |minhas )?rotinas|que rotinas eu tenho|rotinas",
    "en": r"(?:list )?(?:my )?routines|what routines do i have|list (?:my )?routines",
    "es": r"(?:mis )?rutinas|que rutinas tengo",
    "fr": r"(?:mes )?routines|quelles routines j ai",
}
_APAGAR = {
    "pt-BR": r"(?:apaga|apague|remove|remova|exclui|exclua|deleta|delete)(?: a)? rotina (?P<nome>.+)",
    "en": r"(?:delete|remove)(?: the)? routine (?P<nome>.+)",
    "es": r"(?:borra|elimina)(?: la)? rutina (?P<nome>.+)",
    "fr": r"(?:supprime|efface)(?: la)? routine (?P<nome>.+)",
}
_RODAR = {
    "pt-BR": r"(?:executa|execute|roda|rode|inicia|inicie|comeca|comece|liga|ligue|ativa|ative)(?: a)?(?: rotina)? (?P<nome>.+)",
    "en": r"(?:run|start|activate|turn on)(?: the)?(?: routine)? (?P<nome>.+)",
    "es": r"(?:ejecuta|inicia|activa)(?: la)?(?: rutina)? (?P<nome>.+)",
    "fr": r"(?:lance|demarre|active)(?: la)?(?: routine)? (?P<nome>.+)",
}
_FOCO = {
    "modo foco",
    "modo de foco",
    "modo concentracao",
    "focus mode",
    "modo concentracion",
    "mode concentration",
    "mode focus",
}
_PREFIXO = re.compile(
    r"^(?:(?:ei|oi|ok|hey)\s+)?(?:nicx|nix|nics)?[\s,]*(?:por favor|please|por favor,)?\s*"
)


def normalizar_mesmo_tamanho(texto: str) -> str:
    """Minúsculas e sem acento; pontuação vira espaço, menos ':' ',' ';'. Mesmo tamanho."""
    saida = []
    for c in texto:
        base = unicodedata.normalize("NFKD", c)[0].lower() if c.strip() else " "
        saida.append(base if (base.isalnum() or base in ":,;") else " ")
    return "".join(saida)


def _codigos(codigo: str) -> list[str]:
    return ["pt-BR"] if codigo == "pt-BR" else [codigo, "pt-BR"]


def parse(texto: str, codigo: str = "pt-BR") -> Optional[Action]:
    """Action('rotina', op=criar|listar|apagar|rodar|foco, target=nome, site=passos) ou None."""
    from nicx.rotinas import armazenamento

    norm = normalizar_mesmo_tamanho(texto.strip())
    original = texto.strip()
    m0 = _PREFIXO.match(norm)
    inicio = m0.end() if m0 else 0
    corpo, corpo_orig = norm[inicio:], original[inicio:]
    simples = " ".join(
        corpo.replace(",", " ").replace(";", " ").replace(":", " ").split()
    )
    if not simples or len(simples) > 600:
        return None
    for cod in _codigos(codigo):
        padrao = _CRIAR.get(cod)
        m = re.fullmatch(padrao, corpo.strip()) if padrao else None
        if m:
            desloc = len(corpo) - len(corpo.lstrip())
            resto = corpo_orig[desloc + m.start("resto") : desloc + m.end("resto")]
            return Action(
                "rotina",
                op="criar",
                target=" ".join(m.group("nome").split()),
                site=resto.strip(),
            )
    if len(simples) > 120:
        return None
    rotina = armazenamento.por_frase(simples)
    if rotina is not None:
        return Action("rotina", op="rodar", target=rotina.id)
    if simples in _FOCO:
        return Action("rotina", op="foco")
    for cod in _codigos(codigo):
        if _LISTAR.get(cod) and re.fullmatch(_LISTAR[cod], simples):
            return Action("rotina", op="listar")
        m = re.fullmatch(_APAGAR[cod], simples) if cod in _APAGAR else None
        if m:
            return Action("rotina", op="apagar", target=m.group("nome"))
        m = re.fullmatch(_RODAR[cod], simples) if cod in _RODAR else None
        if m:
            nome = re.sub(r"^(?:a|o|the|la|el|le) ", "", m.group("nome"))
            alvo = armazenamento.por_frase(nome)
            if alvo is not None:
                return Action("rotina", op="rodar", target=alvo.id)
            if nome in _FOCO:
                return Action("rotina", op="foco")
    return None


__all__ = ["normalizar_mesmo_tamanho", "parse"]
