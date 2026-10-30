"""Resumo do dia: o que aconteceu hoje (ou ontem) num texto curto.

``montar(dia, idioma)`` junta lembretes, compromissos, anotações, pastas
organizadas e projetos do dia e escreve o resumo sem modelo (na hora).
``refinar`` pede ao modelo local para deixar o texto mais natural (só quando
o app pede). ``responder`` atende os pedidos "resumo do dia", "como foi meu
dia?", "o que ficou pendente hoje?" como ação rápida.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any, Optional

from nicx.resumo.montagem import Item, Resumo, agora_local, hoje, montar
from nicx.resumo.textos import codigo, texto

logger = logging.getLogger(__name__)

_PENSAMENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def responder(action: Any) -> Any:
    """Executa ``Action("resumo")`` e devolve o ``Outcome`` para falar.

    O idioma é o atual das ações (o da interface, por ``textos.usando``).
    """
    from nicx.acoes import textos as textos_acoes
    from nicx.acoes.sistema import Outcome

    agora = agora_local()
    dia = agora.date()
    if getattr(action, "op", "") == "ontem":
        dia -= timedelta(days=1)
    resumo = montar(dia, textos_acoes.codigo(), agora=agora)
    pendente = getattr(action, "target", "") == "pendente"
    return Outcome(True, resumo.texto_pendente if pendente else resumo.texto)


def refinar(texto_base: str, idioma: Optional[str], engine: Any, model: str) -> str:
    """O mesmo resumo reescrito pelo modelo local, mais natural.

    Levanta se o modelo falhar; quem chama decide ficar com o texto base.
    """
    from nicx.nucleo.idiomas import PADRAO, instrucao_resposta
    from nicx.nucleo.types import Message, Role

    pedido = (
        texto("refinar", PADRAO)
        + instrucao_resposta(codigo(idioma))
        + "\n\n"
        + texto_base
    )
    result = engine.generate(
        [Message(role=Role.USER, content=pedido)],
        model=model,
        temperature=0.3,
        max_tokens=400,
    )
    conteudo = _PENSAMENTO.sub("", str(result.get("content") or "")).strip()
    if not conteudo:
        raise ValueError("modelo devolveu texto vazio")
    return conteudo


__all__ = [
    "Item",
    "Resumo",
    "agora_local",
    "hoje",
    "montar",
    "refinar",
    "responder",
]
