"""Rotinas em ``~/.nicx/rotinas.json`` (gravação atômica, com histórico e desfazer)."""

from __future__ import annotations

import json
import logging
import os
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from nicx.rotinas.modelo import Rotina, validar

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_T = TypeVar("_T")


def caminho() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "rotinas.json"


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento nem pontuação: como a frase é comparada."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = "".join(c if c.isalnum() else " " for c in texto)
    return " ".join(texto.split())


def _ler() -> list[dict[str, Any]]:
    arquivo = caminho()
    if not arquivo.exists():
        return []
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("rotinas.json ilegível; guardando cópia e começando vazio")
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
        mudancas.registrar("rotinas", antes, itens, lambda d: str(d.get("nome", "")))


def listar() -> list[Rotina]:
    with _LOCK:
        return [Rotina.de_dict(d) for d in _ler()]


def obter(rotina_id: str) -> Optional[Rotina]:
    return next((r for r in listar() if r.id == rotina_id), None)


def por_frase(frase: str) -> Optional[Rotina]:
    """A rotina cujo nome ou frase é o que foi dito (sem acento nem pontuação)."""
    alvo = normalizar(frase)
    if not alvo:
        return None
    for r in listar():
        if alvo in {normalizar(f) for f in [r.nome, *r.frases]}:
            return r
    return None


def _mudar(funcao: Callable[[list[Rotina]], _T], registrar: bool = True) -> _T:
    with _LOCK:
        rotinas = [Rotina.de_dict(d) for d in _ler()]
        resultado = funcao(rotinas)
        _gravar([r.para_dict() for r in rotinas], registrar=registrar)
        return resultado


def criar(rotina: Rotina) -> Rotina:
    validar(rotina)

    def aplicar(rotinas: list[Rotina]) -> Rotina:
        nomes = {normalizar(r.nome) for r in rotinas}
        if normalizar(rotina.nome) in nomes:
            raise ValueError(f"já existe uma rotina chamada {rotina.nome}")
        rotinas.append(rotina)
        return rotina

    return _mudar(aplicar)


def atualizar(rotina_id: str, nova: Rotina) -> Rotina:
    validar(nova)

    def aplicar(rotinas: list[Rotina]) -> Rotina:
        for i, r in enumerate(rotinas):
            if r.id == rotina_id:
                nova.id, nova.criada_em = r.id, r.criada_em
                nova.ultima_execucao, nova.ultimo_agendado = (
                    r.ultima_execucao,
                    r.ultimo_agendado,
                )
                rotinas[i] = nova
                return nova
        raise KeyError(rotina_id)

    return _mudar(aplicar)


def apagar(rotina_id: str) -> bool:
    def aplicar(rotinas: list[Rotina]) -> bool:
        antes = len(rotinas)
        rotinas[:] = [r for r in rotinas if r.id != rotina_id]
        return len(rotinas) != antes

    return _mudar(aplicar)


def marcar(rotina_id: str, **campos: str) -> None:
    """Datas de execução: não é mudança do usuário, não vai para o histórico."""

    def aplicar(rotinas: list[Rotina]) -> None:
        for r in rotinas:
            if r.id == rotina_id:
                for chave, valor in campos.items():
                    setattr(r, chave, valor)

    _mudar(aplicar, registrar=False)


__all__ = [
    "apagar",
    "atualizar",
    "caminho",
    "criar",
    "listar",
    "marcar",
    "normalizar",
    "obter",
    "por_frase",
]
