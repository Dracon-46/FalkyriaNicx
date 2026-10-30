"""O que aconteceu nos projetos num dia (para o resumo do dia).

Contrato: ``resumo_do_dia(dia) -> dict`` com

- ``"atualizados"``: ``list[str]``, nomes dos projetos com atividade no dia
  (do mais recente para o mais antigo);
- ``"concluidas"``: ``list[tuple[str, str]]``, (projeto, pendência concluída
  no dia);
- ``"pendentes"``: ``list[tuple[str, str]]``, (projeto, pendência aberta), no
  máximo 10, as mais recentes primeiro (projetos arquivados ficam de fora).

Sem projetos, as três listas vêm vazias. Nunca levanta erro por arquivo
estragado: o armazenamento já se protege.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Optional

from nicx.projetos.armazenamento import Projetos
from nicx.projetos.modelo import dia_de

MAX_PENDENTES = 10


def resumo_do_dia(dia: date, *, caminho: Optional[str | Path] = None) -> dict[str, Any]:
    projetos = Projetos(caminho).listar(arquivados=True)
    iso = dia.isoformat()

    atualizados: list[str] = []
    concluidas: list[tuple[str, str]] = []
    abertas: list[tuple[str, str, str]] = []
    for projeto in projetos:  # já vem do mais recente para o mais antigo
        teve = (
            iso in projeto.dias_ativos
            or dia_de(projeto.ultima_atividade) == dia
            or dia_de(projeto.criado_em) == dia
            or any(dia_de(d.data) == dia for d in projeto.decisoes)
        )
        for pendencia in projeto.pendencias:
            if pendencia.feita and dia_de(pendencia.feita_em) == dia:
                concluidas.append((projeto.nome, pendencia.texto))
                teve = True
            elif not pendencia.feita and dia_de(pendencia.criada_em) == dia:
                teve = True
            if not pendencia.feita and not projeto.arquivado:
                abertas.append((pendencia.criada_em, projeto.nome, pendencia.texto))
        if teve:
            atualizados.append(projeto.nome)

    abertas.sort(key=lambda item: item[0], reverse=True)
    return {
        "atualizados": atualizados,
        "concluidas": concluidas,
        "pendentes": [(nome, texto) for _, nome, texto in abertas[:MAX_PENDENTES]],
    }


__all__ = ["resumo_do_dia"]
