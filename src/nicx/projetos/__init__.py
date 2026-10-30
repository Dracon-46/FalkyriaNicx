"""Memória de projetos e "continue de onde parei".

Cada projeto guarda objetivo, estado (o ponto atual, em uma frase), pastas,
arquivos importantes, decisões, pendências e próximos passos, tudo em
``~/.nicx/projetos.json`` (só no PC).

- :mod:`.modelo`: o ``Projeto``; :mod:`.armazenamento`: o arquivo, com
  trava entre processos e gravação atômica; :mod:`.busca`: nome tolerante;
- :mod:`.deteccao`: o projeto da janela em uso (pasta do VS Code), git e
  arquivos recentes, e a marca de atividade (no máximo de tempos em tempos);
- :mod:`.pedidos` + :mod:`.servico`: as frases no chat (pt, en, es, fr);
  respostas na hora em :mod:`.textos` (7 idiomas);
- :mod:`.continuar`: o resumo que vai ao modelo em "continue de onde parei";
- :mod:`.ferramenta`: a ferramenta ``projetos`` do modelo;
- :mod:`.memoria`: decisões/pendências ditas de passagem na conversa;
- :mod:`.diario`: ``resumo_do_dia`` para o resumo do dia.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def resumo_do_dia(dia: date) -> dict[str, Any]:
    """Projetos atualizados, pendências concluídas e abertas no *dia*.

    Ver :func:`nicx.projetos.diario.resumo_do_dia` (o contrato).
    """
    from nicx.projetos.diario import resumo_do_dia as _resumo

    return _resumo(dia)


__all__ = ["resumo_do_dia"]
