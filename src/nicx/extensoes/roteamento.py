"""Quando a mensagem pede uma extensão, as ferramentas vão para o modelo.

Com ``[agent] tools_on_demand`` a lista de ferramentas só segue quando a
mensagem parece precisar. Servidores MCP e habilidades são do usuário, então as
palavras dos nomes deles ("github", "postgres", "issue", "planilha_de_notas")
também contam.
"""

from __future__ import annotations

import re

from nicx.acoes.intencoes import normalize

# Palavras comuns demais nos nomes de ferramentas para decidir sozinhas.
_GENERICAS = frozenset(
    {
        "create", "delete", "update", "list", "read", "write", "search", "file",
        "files", "get", "set", "run", "tool", "server", "with", "from", "info",
        "data", "item", "items", "page", "pages", "text", "name", "open",
        "close", "query", "skill", "mcp", "para", "como", "fazer", "criar",
    }
)  # fmt: skip


def _palavras(nome: str) -> set[str]:
    partes = re.split(r"[^a-z0-9]+", normalize(nome).replace("_", " "))
    return {p for p in partes if len(p) >= 4 and p not in _GENERICAS}


def palavras() -> set[str]:
    from nicx.extensoes import mcp

    saida: set[str] = set()
    for ferramenta, (servidor, _risco) in mcp._FERRAMENTAS.items():
        saida |= _palavras(ferramenta) | _palavras(servidor)
    try:
        from nicx.extensoes import habilidades

        for nome in habilidades.nomes_ativos():
            saida |= _palavras(nome)
    except Exception:  # noqa: BLE001 - habilidades são opcionais aqui
        pass
    return saida


def mencionada(texto: str) -> bool:
    chaves = palavras()
    if not chaves:
        return False
    return bool(set(re.split(r"[^a-z0-9]+", normalize(texto))) & chaves)


__all__ = ["mencionada", "palavras"]
