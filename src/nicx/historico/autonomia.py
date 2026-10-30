"""Níveis de autonomia: o que o Nicx faz sozinho e o que pede "confirmo" antes.

A regra fica no código (``nicx.acoes.sistema.run`` e ``ToolExecutor``), não no
"bom comportamento" do modelo: um texto malicioso numa página não convence o
Nicx a pular a confirmação.

Riscos:
- ``leitura``: só consulta (hora, bateria, ler arquivo, pesquisar na web).
- ``leve``: muda pouco e tem desfazer (lembrete, anotação, abrir app, volume).
- ``moderado``: mexe em arquivos, projetos ou apaga em lote (fechar app,
  apagar anotações, organizar pasta, escrever arquivo).
- ``alto``: desligar, reiniciar, rodar comandos no terminal, git que grava.

Níveis:
- ``observador``: só ``leitura`` passa direto.
- ``assistido`` (padrão): ``leitura`` e ``leve`` passam direto.
- ``autonomo``: tudo menos ``alto`` passa direto.
``alto`` pede confirmação em qualquer nível.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

NIVEIS = ("observador", "assistido", "autonomo")
PADRAO = "assistido"
RISCOS = ("leitura", "leve", "moderado", "alto")

# o que cada nível deixa passar sem perguntar
_LIBERADO = {
    "observador": {"leitura"},
    "assistido": {"leitura", "leve"},
    "autonomo": {"leitura", "leve", "moderado"},
}

# ações rápidas (nicx.acoes.intencoes.Action.kind)
_RISCO_ACAO = {
    "time": "leitura",
    "date": "leitura",
    "battery": "leitura",
    "status": "leitura",
    "resumo": "leitura",
    "remind_list": "leitura",
    "notes_list": "leitura",
    "agenda_list": "leitura",
    "folder_list": "leitura",
    "file_find": "leitura",
    "file_latest": "leitura",
    "historico": "leitura",
    "autonomia": "leitura",
    "confirm": "leitura",
    "deny": "leitura",
    "volume": "leve",
    "media": "leve",
    "open": "leve",
    "search": "leve",
    "youtube": "leve",
    "folder": "leve",
    "file_open": "leve",
    "screenshot": "leve",
    "lock": "leve",
    "remind": "leve",
    "remind_cancel": "leve",
    "note_add": "leve",
    "agenda_add": "leve",
    "agenda_cancel": "leve",
    "agenda_export": "leve",
    "undo": "leve",
    "organize_undo": "leve",
    "remind_clear": "moderado",
    "notes_clear": "moderado",
    "close": "moderado",
    "organize": "moderado",
    "power": "alto",
}

# ferramentas do modelo que entregam o trabalho às ações rápidas: a regra é
# aplicada lá (em nicx.acoes.sistema.run), para não perguntar duas vezes
DELEGADAS = frozenset({"controle_pc", "lembrete", "agenda", "arquivos"})

_RISCO_FERRAMENTA = {
    "shell_exec": "alto",
    "docker_shell_exec": "alto",
    "code_interpreter": "alto",
    "code_interpreter_docker": "alto",
    "repl": "alto",
    "git_commit": "alto",
    "file_write": "moderado",
    "apply_patch": "moderado",
    "channel_send": "moderado",
    "browser_click": "moderado",
    "browser_type": "moderado",
    "execute_pending_actions": "moderado",
    "agent_spawn": "moderado",
    "agent_kill": "moderado",
    "projetos": "leve",
    "memory_store": "leve",
    "memory_manage": "leve",
    "memory_index": "leve",
    "kg_add_entity": "leve",
    "kg_add_relation": "leve",
    "skill_manage": "leve",
    "user_profile_manage": "leve",
    "record_decision": "leve",
    "queue_action": "leve",
}


def nivel_atual() -> str:
    try:
        from nicx.nucleo.config import load_config

        nivel = str(load_config().autonomia.nivel or PADRAO).strip().lower()
    except Exception:  # noqa: BLE001 - config ilegível: fica no padrão
        logger.debug("Nível de autonomia ilegível", exc_info=True)
        return PADRAO
    nivel = nivel.replace("ô", "o")
    return nivel if nivel in NIVEIS else PADRAO


def risco_acao(kind: str, op: str = "") -> str:
    if kind == "power" and op == "abort":
        return "leitura"  # cancelar um desligamento nunca pede confirmação
    return _RISCO_ACAO.get(kind, "leve")


def risco_ferramenta(
    nome: str,
    parametros: Optional[Mapping[str, Any]] = None,
    *,
    pede_confirmacao: bool = False,
) -> str:
    """Risco de uma chamada de ferramenta do modelo."""
    if pede_confirmacao:
        return "alto"
    if nome in _RISCO_FERRAMENTA:
        return _RISCO_FERRAMENTA[nome]
    if nome == "http_request":
        metodo = str((parametros or {}).get("method", "GET")).upper()
        return "leitura" if metodo in {"GET", "HEAD", "OPTIONS"} else "moderado"
    return "leitura"


def precisa_confirmar(risco: str, nivel: Optional[str] = None) -> bool:
    if risco == "alto":
        return True
    return risco not in _LIBERADO.get(nivel or nivel_atual(), _LIBERADO[PADRAO])


def descricao_niveis() -> list[dict[str, Any]]:
    """Para a tela: o que cada nível faz sozinho."""
    return [
        {"nivel": n, "liberado": sorted(_LIBERADO[n], key=RISCOS.index)} for n in NIVEIS
    ]


__all__ = [
    "DELEGADAS",
    "NIVEIS",
    "PADRAO",
    "RISCOS",
    "descricao_niveis",
    "nivel_atual",
    "precisa_confirmar",
    "risco_acao",
    "risco_ferramenta",
]
