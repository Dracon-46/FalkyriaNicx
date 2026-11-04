"""Assistente: nome, instruções, ferramentas permitidas e se usa a memória.

``ferramentas`` lista os nomes das ferramentas do Nicx que o assistente pode
usar; ``["*"]`` quer dizer todas e a lista vazia, nenhuma (a resposta sai
direto do modelo, mais rápida). Instruções longas custam tempo: neste PC cada
token de entrada é relido em todo pedido.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

MAX_NOME = 40
MAX_DESCRICAO = 200
MAX_INSTRUCOES = 2000
MAX_SAUDACAO = 200
MAX_FERRAMENTAS = 30
TODAS = "*"


class AssistenteInvalido(ValueError):
    """Campo fora do limite; a mensagem diz qual."""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _novo_id() -> str:
    return uuid.uuid4().hex[:10]


def _linha(valor: Any) -> str:
    return " ".join(str(valor or "").split())


@dataclass
class Assistente:
    nome: str
    instrucoes: str
    descricao: str = ""
    ferramentas: list[str] = field(default_factory=list)
    memoria: bool = True
    saudacao: str = ""
    modelo: str = ""  # id do modelo pronto de onde saiu ("estudos"...), se saiu de um
    id: str = field(default_factory=_novo_id)
    criado_em: str = field(default_factory=agora)
    atualizado_em: str = field(default_factory=agora)

    @property
    def todas_as_ferramentas(self) -> bool:
        return TODAS in self.ferramentas

    def permite(self, ferramenta: str) -> bool:
        return self.todas_as_ferramentas or ferramenta in self.ferramentas

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Assistente":
        ferramentas = dados.get("ferramentas") or []
        if not isinstance(ferramentas, list):
            ferramentas = []
        return cls(
            nome=_linha(dados.get("nome")),
            instrucoes=str(dados.get("instrucoes", "") or "").strip(),
            descricao=_linha(dados.get("descricao")),
            ferramentas=list(
                dict.fromkeys(str(f).strip() for f in ferramentas if str(f).strip())
            ),
            memoria=bool(dados.get("memoria", True)),
            saudacao=_linha(dados.get("saudacao")),
            modelo=str(dados.get("modelo", "") or ""),
            id=str(dados.get("id") or _novo_id()),
            criado_em=str(dados.get("criado_em") or agora()),
            atualizado_em=str(dados.get("atualizado_em") or agora()),
        )


def validar(assistente: Assistente) -> None:
    if not assistente.nome:
        raise AssistenteInvalido("o assistente precisa de um nome")
    if len(assistente.nome) > MAX_NOME:
        raise AssistenteInvalido(f"o nome passa de {MAX_NOME} caracteres")
    if not assistente.instrucoes:
        raise AssistenteInvalido("faltam as instruções")
    if len(assistente.instrucoes) > MAX_INSTRUCOES:
        raise AssistenteInvalido(f"as instruções passam de {MAX_INSTRUCOES} caracteres")
    if len(assistente.descricao) > MAX_DESCRICAO:
        raise AssistenteInvalido(f"a descrição passa de {MAX_DESCRICAO} caracteres")
    if len(assistente.saudacao) > MAX_SAUDACAO:
        raise AssistenteInvalido(f"a saudação passa de {MAX_SAUDACAO} caracteres")
    if len(assistente.ferramentas) > MAX_FERRAMENTAS:
        raise AssistenteInvalido("ferramentas demais")


__all__ = [
    "MAX_DESCRICAO",
    "MAX_INSTRUCOES",
    "MAX_NOME",
    "MAX_SAUDACAO",
    "TODAS",
    "Assistente",
    "AssistenteInvalido",
    "agora",
    "validar",
]
