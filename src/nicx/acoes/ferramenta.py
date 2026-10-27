"""Ferramenta ``controle_pc``: as mesmas ações, para o modelo usar.

Os comandos diretos ("aumenta o volume") nem chegam ao modelo; esta
ferramenta cobre o resto ("tá muito alto esse som", "abre o editor de texto").
A descrição é curta de propósito: cada token aqui vai em toda pergunta.
"""

from __future__ import annotations

from typing import Any

from nicx.acoes.intencoes import APPS, STEP_NORMAL, Action, normalize
from nicx.acoes.sistema import run
from nicx.ferramentas._stubs import BaseTool, ToolSpec
from nicx.nucleo.registry import ToolRegistry
from nicx.nucleo.types import ToolResult

_ACTIONS = {
    "volume_mais": ("volume", "up"),
    "volume_menos": ("volume", "down"),
    "volume_definir": ("volume", "set"),
    "mudo": ("volume", "mute"),
    "midia_pausar_tocar": ("media", "toggle"),
    "midia_proxima": ("media", "next"),
    "midia_anterior": ("media", "prev"),
    "abrir": ("open", ""),
    "abrir_pasta": ("folder", ""),
    "fechar_app": ("close", ""),
    "anotar": ("note_add", ""),
    "ler_anotacoes": ("notes_list", ""),
    "estado_pc": ("status", ""),
    "print_tela": ("screenshot", ""),
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
                "Controla este PC: volume, mídia, abrir app/site/pasta, fechar app,"
                " anotar, estado do PC, print, bloquear tela."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": list(_ACTIONS)},
                    "valor": {"type": "integer", "description": "volume 0-100"},
                    "alvo": {
                        "type": "string",
                        "description": "app, site ou pasta; ou o texto a anotar",
                    },
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
        elif kind in ("folder", "close"):
            from nicx.acoes.rotinas import _FOLDER_ALIASES, CLOSABLE, FOLDERS

            target = normalize(str(params.get("alvo", "")))
            target = _FOLDER_ALIASES.get(target, target) if kind == "folder" else target
            known_map = FOLDERS if kind == "folder" else CLOSABLE
            if target not in known_map:
                known = ", ".join(sorted(known_map))
                return ToolResult(
                    self.tool_id, f"Não conheço '{target}'. Conheço: {known}.", False
                )
            action = Action(kind, target=target)
        elif kind == "note_add":
            text = str(params.get("alvo", "")).strip()
            if not text:
                return ToolResult(self.tool_id, "Faltou o texto a anotar.", False)
            action = Action(kind, target=text)
        elif kind == "volume" and op in ("up", "down"):
            action = Action(kind, op, STEP_NORMAL)
        else:
            action = Action(kind, op, int(value) if value is not None else None)
        outcome = run(action)
        return ToolResult(self.tool_id, outcome.message, success=outcome.ok)


@ToolRegistry.register("lembrete")
class ReminderTool(BaseTool):
    """Marca um lembrete; o Nicx avisa com notificação e voz na hora."""

    tool_id = "lembrete"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="lembrete",
            description="Marca um lembrete ou timer. O Nicx avisa na hora.",
            parameters={
                "type": "object",
                "properties": {
                    "quando": {
                        "type": "string",
                        "description": "'em 10 minutos', 'às 15h', 'amanhã às 8'",
                    },
                    "mensagem": {"type": "string", "description": "do que lembrar"},
                },
                "required": ["quando", "mensagem"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        from nicx.acoes.tempo import parse_when

        when = parse_when(normalize(str(params.get("quando", ""))))
        message = str(params.get("mensagem", "")).strip()
        if when is None:
            return ToolResult(
                self.tool_id,
                "Não entendi o horário. Use 'em 10 minutos', 'às 15h'"
                " ou 'amanhã às 8'.",
                False,
            )
        if not message:
            return ToolResult(self.tool_id, "Faltou dizer do que lembrar.", False)
        outcome = run(Action("remind", target=message, when=when))
        return ToolResult(self.tool_id, outcome.message, success=outcome.ok)
