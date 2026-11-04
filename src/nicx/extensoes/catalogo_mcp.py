"""Servidores MCP conhecidos, para adicionar com um clique (tela e ``nicx add``).

Todos rodam com ``npx`` (precisa do Node.js). ``env`` lista as variáveis que o
servidor pede (chave de API, token); ``pede_args`` diz o que o usuário completa
nos argumentos (a pasta do ``filesystem``). Os nomes e descrições na tela vêm
das traduções do frontend, pela ``chave``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Modelo:
    chave: str
    descricao: str  # em inglês, para a CLI; a tela traduz pela chave
    args: tuple[str, ...]
    env: tuple[str, ...] = ()
    pede_args: str = ""  # o que completar nos argumentos ("pasta"), se algo
    confianca: str = "perguntar"
    comando: str = "npx"

    def para_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["args"] = list(self.args)
        dados["env"] = list(self.env)
        return dados


CATALOGO: tuple[Modelo, ...] = (
    Modelo(
        "filesystem",
        "Read and write files in the folders you choose",
        ("-y", "@modelcontextprotocol/server-filesystem"),
        pede_args="pasta",
    ),
    Modelo(
        "memory",
        "Knowledge graph memory",
        ("-y", "@modelcontextprotocol/server-memory"),
    ),
    Modelo(
        "sequential-thinking",
        "Step-by-step reasoning helper",
        ("-y", "@modelcontextprotocol/server-sequential-thinking"),
        confianca="livre",
    ),
    Modelo(
        "github",
        "GitHub API (repos, issues, PRs)",
        ("-y", "@modelcontextprotocol/server-github"),
        env=("GITHUB_PERSONAL_ACCESS_TOKEN",),
    ),
    Modelo(
        "slack",
        "Slack workspace integration",
        ("-y", "@modelcontextprotocol/server-slack"),
        env=("SLACK_BOT_TOKEN",),
    ),
    Modelo(
        "postgres",
        "PostgreSQL database (read-only queries)",
        ("-y", "@modelcontextprotocol/server-postgres"),
        pede_args="conexao",
    ),
    Modelo(
        "brave-search",
        "Brave web search",
        ("-y", "@modelcontextprotocol/server-brave-search"),
        env=("BRAVE_API_KEY",),
    ),
    Modelo(
        "puppeteer",
        "Browser automation via Puppeteer",
        ("-y", "@modelcontextprotocol/server-puppeteer"),
    ),
    Modelo(
        "google-maps",
        "Google Maps API",
        ("-y", "@modelcontextprotocol/server-google-maps"),
        env=("GOOGLE_MAPS_API_KEY",),
    ),
)


def modelo(chave: str) -> Optional[Modelo]:
    return next((m for m in CATALOGO if m.chave == chave), None)


__all__ = ["CATALOGO", "Modelo", "modelo"]
