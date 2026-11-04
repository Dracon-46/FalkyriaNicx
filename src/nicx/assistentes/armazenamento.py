"""Assistentes em ``~/.nicx/assistentes.json`` (gravação atômica, com histórico
e desfazer). O ativo fica à parte, em ``assistente_ativo.txt``: trocar de
assistente não vira linha no histórico."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from nicx.assistentes.modelo import Assistente, AssistenteInvalido, agora, validar
from nicx.rotinas.armazenamento import normalizar

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_T = TypeVar("_T")


def caminho() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "assistentes.json"


def _caminho_ativo() -> Path:
    return caminho().with_name("assistente_ativo.txt")


def _ler() -> list[dict[str, Any]]:
    arquivo = caminho()
    if not arquivo.exists():
        return []
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("assistentes.json ilegível; guardando cópia e começando vazio")
        try:
            arquivo.replace(arquivo.with_suffix(".json.corrompido"))
        except OSError:
            pass
        return []
    return [d for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []


def _gravar(itens: list[dict[str, Any]], registrar: bool = True) -> None:
    from nicx.historico import mudancas

    antes = _ler() if registrar and not mudancas.silenciado() else None
    arquivo = caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, arquivo)
    if antes is not None:
        mudancas.registrar(
            "assistentes", antes, itens, lambda d: str(d.get("nome", ""))
        )


def listar() -> list[Assistente]:
    with _LOCK:
        return [Assistente.de_dict(d) for d in _ler()]


def obter(assistente_id: str) -> Optional[Assistente]:
    return next((a for a in listar() if a.id == assistente_id), None)


def por_nome(nome: str) -> Optional[Assistente]:
    """O assistente com esse nome (sem acento, maiúsculas nem pontuação).

    Também acha por uma palavra do nome ("tutor" acha "Tutor de estudos")
    quando só um assistente combina.
    """
    alvo = normalizar(nome)
    if not alvo:
        return None
    todos = listar()
    for a in todos:
        if normalizar(a.nome) == alvo:
            return a
    if len(alvo) < 3:
        return None
    parecidos = [a for a in todos if f" {alvo} " in f" {normalizar(a.nome)} "]
    return parecidos[0] if len(parecidos) == 1 else None


def _mudar(funcao: Callable[[list[Assistente]], _T]) -> _T:
    with _LOCK:
        assistentes = [Assistente.de_dict(d) for d in _ler()]
        resultado = funcao(assistentes)
        _gravar([a.para_dict() for a in assistentes])
        return resultado


def _nome_livre(nome: str, assistentes: list[Assistente], exceto: str = "") -> None:
    usados = {normalizar(a.nome) for a in assistentes if a.id != exceto}
    if normalizar(nome) in usados:
        raise AssistenteInvalido(f"já existe um assistente chamado {nome}")


def criar(assistente: Assistente) -> Assistente:
    validar(assistente)

    def aplicar(assistentes: list[Assistente]) -> Assistente:
        _nome_livre(assistente.nome, assistentes)
        assistentes.append(assistente)
        return assistente

    return _mudar(aplicar)


def atualizar(assistente_id: str, novo: Assistente) -> Assistente:
    validar(novo)

    def aplicar(assistentes: list[Assistente]) -> Assistente:
        for i, a in enumerate(assistentes):
            if a.id == assistente_id:
                _nome_livre(novo.nome, assistentes, exceto=a.id)
                novo.id, novo.criado_em = a.id, a.criado_em
                novo.atualizado_em = agora()
                assistentes[i] = novo
                return novo
        raise KeyError(assistente_id)

    return _mudar(aplicar)


def apagar(assistente_id: str) -> bool:
    def aplicar(assistentes: list[Assistente]) -> bool:
        antes = len(assistentes)
        assistentes[:] = [a for a in assistentes if a.id != assistente_id]
        return len(assistentes) != antes

    apagou = _mudar(aplicar)
    if apagou and id_ativo() == assistente_id:
        definir_ativo(None)
    return apagou


# ------------------------------------------------------------------ ativo
def id_ativo() -> str:
    try:
        return _caminho_ativo().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def ativo() -> Optional[Assistente]:
    """O assistente em uso (None = o Nicx de sempre, ou o ativo foi apagado)."""
    atual = id_ativo()
    return obter(atual) if atual else None


def definir_ativo(assistente_id: Optional[str]) -> None:
    arquivo = _caminho_ativo()
    with _LOCK:
        if not assistente_id:
            arquivo.unlink(missing_ok=True)
            return
        if obter(assistente_id) is None:
            raise KeyError(assistente_id)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(assistente_id, encoding="utf-8")


__all__ = [
    "apagar",
    "ativo",
    "atualizar",
    "caminho",
    "criar",
    "definir_ativo",
    "id_ativo",
    "listar",
    "obter",
    "por_nome",
]
