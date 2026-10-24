"""Ferramenta ``controle_pc``: as mesmas ações, para o modelo usar.

Os comandos diretos ("aumenta o volume") nem chegam ao modelo; esta
ferramenta cobre o resto ("tá muito alto esse som", "abre o editor de texto").
A descrição é curta de propósito: cada token aqui vai em toda pergunta.
"""

from __future__ import annotations

from typing import Any

from nicx.acoes.intencoes import APPS, STEP_NORMAL, Action, normalize
from nicx.acoes.sistema import run
from nicx.core.registry import ToolRegistry
from nicx.core.types import ToolResult
from nicx.tools._stubs import BaseTool, ToolSpec

_ACTIONS = {
    "volume_mais": ("volume", "up"),
    "volume_menos": ("volume", "down"),
    "volume_definir": ("volume", "set"),
    "mudo": ("volume", "mute"),
    "midia_pausar_tocar": ("media", "toggle"),
    "midia_proxima": ("media", "next"),
    "midia_anterior": ("media", "prev"),
    "abrir": ("open", ""),
    "bloquear_tela": ("lock", ""),
}


@ToolRegistry.register("controle_pc")
class ComputerControlTool(BaseTool):
    """Volume, mídia, abrir apps e sites, bloquear a tela."""

    tool_id = "controle_pc"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="controle_pc",
            description=(
                "Controla este PC: volume, mídia, abrir app/site, bloquear tela."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": list(_ACTIONS)},
                    "valor": {"type": "integer", "description": "volume 0-100"},
                    "alvo": {"type": "string", "description": "app ou site a abrir"},
                },
                "required": ["acao"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        name = str(params.get("acao", ""))
        if name not in _ACTIONS:
            return ToolResult(self.tool_id, f"Ação desconhecida: {name}", success=False)
        kind, op = _ACTIONS[name]
        value = params.get("valor")
        if kind == "open":
            target = normalize(str(params.get("alvo", "")))
            if target not in APPS:
                known = ", ".join(sorted({a.label for a in APPS.values()}))
                return ToolResult(
                    self.tool_id,
                    f"Não sei abrir '{target}'. Sei abrir: {known}.",
                    False,
                )
            action = Action("open", target=target)
        elif kind == "volume" and op in ("up", "down"):
            action = Action(kind, op, STEP_NORMAL)
        else:
            action = Action(kind, op, int(value) if value is not None else None)
        outcome = run(action)
        return ToolResult(self.tool_id, outcome.message, success=outcome.ok)
