"""Usar, listar e trocar de assistente; montar um a partir de uma descrição.

Montar é o único passo com modelo: o modelo local propõe nome, descrição,
instruções e ferramentas (só entre as que existem no PC), e o código valida e
salva. O resto não usa modelo.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from nicx.acoes.intencoes import Action
from nicx.acoes.sistema import Outcome
from nicx.assistentes import armazenamento, textos
from nicx.assistentes.modelo import (
    MAX_DESCRICAO,
    MAX_INSTRUCOES,
    MAX_NOME,
    MAX_SAUDACAO,
    Assistente,
    AssistenteInvalido,
)

logger = logging.getLogger(__name__)
_PENSAMENTO = re.compile(r"<think>.*?</think>", re.S)


def _nomes(assistentes: list[Assistente]) -> str:
    return ", ".join(a.nome for a in assistentes)


def executar(action: Action, idioma: Optional[str] = None) -> Outcome:
    """As ações rápidas: usar, sair, listar e qual."""
    if action.op == "sair":
        armazenamento.definir_ativo(None)
        return Outcome(True, textos.texto("desativado", idioma))
    if action.op == "qual":
        atual = armazenamento.ativo()
        if atual is None:
            return Outcome(True, textos.texto("nenhum_ativo", idioma))
        return Outcome(True, textos.texto("qual", idioma, nome=atual.nome))
    todos = armazenamento.listar()
    if action.op == "listar":
        if not todos:
            return Outcome(True, textos.texto("sem_assistentes", idioma))
        return Outcome(True, textos.texto("lista", idioma, lista=_nomes(todos)))
    # usar
    if not todos:
        return Outcome(False, textos.texto("sem_assistentes", idioma))
    achado = armazenamento.por_nome(action.target)
    if achado is None:
        sugestao = textos.texto("sugestao", idioma, lista=_nomes(todos))
        return Outcome(
            False,
            textos.texto("nao_achei", idioma, nome=action.target, sugestao=sugestao),
        )
    if armazenamento.id_ativo() == achado.id:
        return Outcome(True, textos.texto("ja_ativo", idioma, nome=achado.nome))
    armazenamento.definir_ativo(achado.id)
    mensagem = textos.texto("ativado", idioma, nome=achado.nome)
    if achado.saudacao:
        mensagem = f"{mensagem} {achado.saudacao}"
    return Outcome(True, mensagem)


# ------------------------------------------------------------- montar (modelo local)
def _pedido_modelo(descricao: str, ferramentas: dict[str, str], idioma: str) -> str:
    from nicx.nucleo.idiomas import instrucao_resposta

    lista = "\n".join(f"- {nome}: {desc[:120]}" for nome, desc in ferramentas.items())
    return (
        "Monte um assistente para o pedido abaixo. Responda SÓ com um objeto JSON, "
        "sem texto antes ou depois, no formato "
        '{"nome": "...", "descricao": "...", "instrucoes": "...", '
        '"ferramentas": [], "saudacao": "..."}. '
        f"nome: até {MAX_NOME} caracteres. descricao: uma frase. instrucoes: até 600 "
        'caracteres, na segunda pessoa ("Explique...", "Responda..."), dizendo '
        "como o assistente deve agir e responder. saudacao: uma frase curta. "
        "ferramentas: só nomes desta lista e só se o assistente precisar delas "
        "(deixe vazio se não precisar; sem ferramentas ele responde mais rápido):\n"
        f"{lista or '(nenhuma)'}"
        + instrucao_resposta(idioma)
        + f"\n\nPedido: {descricao}"
    )


def ler_proposta(resposta: str, ferramentas: dict[str, str]) -> Assistente:
    """Tira o objeto JSON da resposta do modelo (tolera texto em volta)."""
    texto = _PENSAMENTO.sub("", resposta or "")
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim <= inicio:
        raise AssistenteInvalido("o modelo não devolveu o assistente")
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except ValueError as exc:
        raise AssistenteInvalido("o modelo devolveu um assistente ilegível") from exc
    if not isinstance(dados, dict):
        raise AssistenteInvalido("o modelo não devolveu o assistente")
    escolhidas = dados.get("ferramentas") or []
    if not isinstance(escolhidas, list):
        escolhidas = []
    assistente = Assistente.de_dict(
        {
            "nome": str(dados.get("nome") or "")[:MAX_NOME],
            "descricao": str(dados.get("descricao") or "")[:MAX_DESCRICAO],
            "instrucoes": str(dados.get("instrucoes") or "")[:MAX_INSTRUCOES],
            "saudacao": str(dados.get("saudacao") or "")[:MAX_SAUDACAO],
            "ferramentas": [f for f in escolhidas if str(f) in ferramentas],
        }
    )
    if not assistente.nome or not assistente.instrucoes:
        raise AssistenteInvalido("o modelo não devolveu nome e instruções")
    return assistente


def propor(
    descricao: str,
    idioma: str,
    engine: Any,
    model: str,
    ferramentas: Optional[dict[str, str]] = None,
) -> Assistente:
    """Pede o assistente ao modelo local, sem salvar. Levanta ``AssistenteInvalido``."""
    from nicx.nucleo.types import Message, Role

    ferramentas = ferramentas or {}
    resultado = engine.generate(
        [
            Message(
                role=Role.USER,
                content=_pedido_modelo(descricao, ferramentas, idioma),
            )
        ],
        model=model,
        temperature=0.3,
        max_tokens=700,
    )
    return ler_proposta(str(resultado.get("content") or ""), ferramentas)


def nome_livre(assistente: Assistente) -> Assistente:
    """Acrescenta " 2", " 3"... ao nome se já houver um assistente com ele."""
    from nicx.rotinas.armazenamento import normalizar

    usados = {normalizar(a.nome) for a in armazenamento.listar()}
    base, n = assistente.nome, 2
    while normalizar(assistente.nome) in usados:
        sufixo = f" {n}"
        assistente.nome = base[: MAX_NOME - len(sufixo)] + sufixo
        n += 1
    return assistente


def montar(
    descricao: str,
    idioma: str,
    engine: Any,
    model: str,
    ferramentas: Optional[dict[str, str]] = None,
) -> str:
    """'cria um assistente que...': propõe, salva e diz como usar."""
    assistente = nome_livre(propor(descricao, idioma, engine, model, ferramentas))
    armazenamento.criar(assistente)
    return textos.texto(
        "criado", idioma, nome=assistente.nome, descricao=assistente.descricao
    ).replace("  ", " ")


def ferramentas_do_agente(agent: Any) -> dict[str, str]:
    """Nome -> descrição das ferramentas que o agente do servidor tem."""
    saida: dict[str, str] = {}
    for tool in getattr(agent, "_tools", None) or []:
        spec = getattr(tool, "spec", None)
        if spec is not None and getattr(spec, "name", ""):
            saida[spec.name] = " ".join(str(getattr(spec, "description", "")).split())
    return saida


__all__ = [
    "executar",
    "ferramentas_do_agente",
    "ler_proposta",
    "montar",
    "nome_livre",
    "propor",
]
