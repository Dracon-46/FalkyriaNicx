"""Ações rápidas: comandos que o Nicx executa sem passar pelo modelo.

"Aumenta o volume", "pausa a música", "abre o YouTube", "que horas são":
reconhecidos por padrão de frase e executados na hora, com resposta curta.
Respondem em menos de 1 s e não gastam tokens. O que não for comando direto
segue para o modelo, que tem a ferramenta ``controle_pc`` para o resto.
"""

from __future__ import annotations

from typing import Optional

from nicx.acoes.intencoes import Action, parse
from nicx.acoes.sistema import Outcome, run


def handle(text: str) -> Optional[Outcome]:
    """Executa ``text`` se for um comando direto; senão devolve None."""
    action = parse(text)
    return run(action) if action is not None else None


__all__ = ["Action", "Outcome", "handle", "parse", "run"]
