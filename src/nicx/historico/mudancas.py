"""Mudanças em coleções guardadas em JSON (lembretes, agenda, projetos).

Quem grava a coleção chama :func:`registrar` com a lista antes e depois. Daqui
sai uma linha no histórico com o jeito de desfazer: tirar o que entrou, pôr de
volta o que saiu e voltar o que mudou, sem perder o que foi feito depois.

Mudanças feitas dentro de outra (o aviso que um compromisso cria) são
capturadas com :func:`capturar` e desfeitas junto com ela.
"""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger(__name__)

_captura: contextvars.ContextVar[Optional[list[dict[str, Any]]]] = (
    contextvars.ContextVar("nicx_captura", default=None)
)
_silencio: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "nicx_silencio", default=False
)

# coleção -> (tipo no histórico, chave das frases)
_TIPO = {"lembretes": "lembrete", "agenda": "agenda", "projetos": "projeto"}


@contextmanager
def capturar() -> Iterator[list[dict[str, Any]]]:
    """As mudanças feitas no bloco vão para a lista, em vez de virar linhas próprias."""
    lista: list[dict[str, Any]] = []
    token = _captura.set(lista)
    try:
        yield lista
    finally:
        _captura.reset(token)


@contextmanager
def sem_registro() -> Iterator[None]:
    """Nada do bloco vira histórico (usado pelo próprio desfazer)."""
    token = _silencio.set(True)
    try:
        yield
    finally:
        _silencio.reset(token)


def silenciado() -> bool:
    return _silencio.get()


def diferenca(
    colecao: str,
    antes: list[dict[str, Any]],
    depois: list[dict[str, Any]],
    chave: str = "id",
) -> Optional[dict[str, Any]]:
    velhos = {d.get(chave): d for d in antes}
    novos = {d.get(chave): d for d in depois}
    adicionados = [k for k in novos if k not in velhos]
    removidos = [velhos[k] for k in velhos if k not in novos]
    alterados = [velhos[k] for k in velhos if k in novos and novos[k] != velhos[k]]
    if not (adicionados or removidos or alterados):
        return None
    return {
        "colecao": colecao,
        "chave": chave,
        "adicionados": adicionados,
        "removidos": removidos,
        "alterados": alterados,
        "novos": [novos[k] for k in adicionados]
        + [novos[d.get(chave)] for d in alterados],
    }


def registrar(
    colecao: str,
    antes: list[dict[str, Any]],
    depois: list[dict[str, Any]],
    rotulo: Callable[[dict[str, Any]], str],
    *,
    junto: Optional[list[dict[str, Any]]] = None,
    chave: str = "id",
) -> None:
    """Anota a mudança (nunca levanta)."""
    if _silencio.get():
        return
    try:
        mudanca = diferenca(colecao, antes, depois, chave)
        if mudanca is None:
            return
        if junto:
            mudanca["junto"] = junto
        captura = _captura.get()
        if captura is not None:
            captura.append(mudanca)
            return
        from nicx.historico import textos
        from nicx.historico.registro import anotar

        base = _TIPO.get(colecao, colecao)
        if (
            mudanca["adicionados"]
            and not mudanca["removidos"]
            and not mudanca["alterados"]
        ):
            evento, alvo = "criado", mudanca["novos"][0]
            qtd = len(mudanca["adicionados"])
        elif (
            mudanca["removidos"]
            and not mudanca["adicionados"]
            and not mudanca["alterados"]
        ):
            evento, alvo = "cancelado", mudanca["removidos"][0]
            qtd = len(mudanca["removidos"])
        else:
            evento = "alterado"
            alvo = (mudanca["alterados"] or mudanca["removidos"] or mudanca["novos"])[0]
            qtd = 1
        nome = rotulo(alvo)
        if qtd > 1:
            nome = f"{nome} (+{qtd - 1})"
        itens = [rotulo(d) for d in mudanca["novos"] + mudanca["removidos"]][:20]
        # guarda o estado novo só para o desfazer, não para a tela
        mudanca.pop("novos", None)
        anotar(
            base,
            textos.texto(f"{base}_{evento}", texto=nome),
            detalhe={"colecao": colecao, "evento": evento, "itens": itens},
            desfazer={"tipo": "colecao", **mudanca},
        )
    except Exception:  # noqa: BLE001 - o histórico não pode derrubar a gravação
        logger.debug("Mudança em %s não anotada", colecao, exc_info=True)


def inverter(
    mudanca: dict[str, Any], atuais: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Aplica o contrário da mudança sobre a lista atual."""
    chave = mudanca.get("chave", "id")
    tirar = set(mudanca.get("adicionados", []))
    voltar = {d.get(chave): d for d in mudanca.get("alterados", [])}
    resultado = []
    for d in atuais:
        k = d.get(chave)
        if k in tirar:
            continue
        resultado.append(voltar.pop(k, d))
    presentes = {d.get(chave) for d in resultado}
    for d in mudanca.get("removidos", []):
        if d.get(chave) not in presentes:
            resultado.append(d)
    return resultado


__all__ = [
    "capturar",
    "diferenca",
    "inverter",
    "registrar",
    "sem_registro",
    "silenciado",
]
