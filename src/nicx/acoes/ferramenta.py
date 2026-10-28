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
    "tocar_youtube": ("youtube", ""),
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
                        "description": (
                            "app, site ou pasta; o texto a anotar; ou o que tocar"
                            " no YouTube"
                        ),
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
        elif kind in ("note_add", "youtube"):
            text = str(params.get("alvo", "")).strip()
            if not text:
                missing = "o texto a anotar" if kind == "note_add" else "o que tocar"
                return ToolResult(self.tool_id, f"Faltou {missing}.", False)
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


@ToolRegistry.register("agenda")
class AgendaTool(BaseTool):
    """Agenda local do Nicx: marcar, ver, desmarcar e mandar para o calendário."""

    tool_id = "agenda"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="agenda",
            description=(
                "Agenda do usuário neste PC: marcar compromisso (avisa 15 min antes),"
                " ver o que tem num dia, desmarcar, mandar para o calendário."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": ["marcar", "ver", "desmarcar", "exportar"],
                    },
                    "titulo": {
                        "type": "string",
                        "description": "marcar: o compromisso; desmarcar: como achar",
                    },
                    "quando": {
                        "type": "string",
                        "description": "'sexta às 15h', 'amanhã', 'dia 30 às 9h'",
                    },
                },
                "required": ["acao"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        from nicx.acoes.tempo import parse_day, parse_moment

        acao = str(params.get("acao", ""))
        titulo = str(params.get("titulo", "")).strip()
        quando = normalize(str(params.get("quando", "")))
        if acao == "marcar":
            moment = parse_moment(quando) if quando else None
            if moment is None or not titulo:
                return ToolResult(
                    self.tool_id,
                    "Preciso do título e de quando ('sexta às 15h', 'dia 30').",
                    False,
                )
            when, has_time = moment
            action = Action(
                "agenda_add", target=titulo, when=when, op="" if has_time else "dia"
            )
        elif acao == "ver":
            day = parse_day(quando) if quando else None
            if day is not None:
                from datetime import datetime

                when = datetime.combine(day, datetime.min.time())
                action = Action("agenda_list", op="dia", when=when)
            else:
                action = Action("agenda_list", op="proximos")
        elif acao == "desmarcar":
            action = Action("agenda_cancel", target=normalize(f"{titulo} {quando}"))
        elif acao == "exportar":
            action = Action("agenda_export")
        else:
            return ToolResult(self.tool_id, f"Ação desconhecida: {acao}", False)
        outcome = run(action)
        return ToolResult(self.tool_id, outcome.message, success=outcome.ok)


_FILE_KINDS = ["imagem", "print", "video", "musica", "pdf", "documento", "planilha"]


@ToolRegistry.register("arquivos")
class FilesTool(BaseTool):
    """Arquivos do usuário: procurar, abrir, listar pasta e organizar."""

    tool_id = "arquivos"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="arquivos",
            description=(
                "Arquivos do usuário neste PC (Área de Trabalho, Documentos, Downloads,"
                " Imagens, Vídeos, Músicas, OneDrive): procurar pelo nome, abrir com o"
                " programa padrão, abrir o mais recente de um tipo, listar uma pasta,"
                " organizar uma pasta em subpastas por tipo (pede confirmação) e"
                " desfazer. Para ler o conteúdo de um arquivo achado, use file_read."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": [
                            "procurar",
                            "abrir",
                            "abrir_mais_recente",
                            "listar_pasta",
                            "organizar_pasta",
                            "desfazer_organizacao",
                        ],
                    },
                    "busca": {"type": "string", "description": "parte do nome"},
                    "tipo": {"type": "string", "enum": _FILE_KINDS},
                    "pasta": {
                        "type": "string",
                        "description": "downloads, documentos, imagens, desktop...",
                    },
                },
                "required": ["acao"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        from nicx.acoes.rotinas import _folder_key

        acao = str(params.get("acao", ""))
        busca = str(params.get("busca", "")).strip()
        tipo = str(params.get("tipo", "") or "")
        tipo = tipo if tipo in _FILE_KINDS else ""
        if acao in ("procurar", "abrir"):
            if not busca:
                return ToolResult(
                    self.tool_id, "Faltou a parte do nome a procurar.", False
                )
            kind = "file_find" if acao == "procurar" else "file_open"
            action = Action(kind, target=busca, op="" if tipo == "print" else tipo)
        elif acao == "abrir_mais_recente":
            action = Action("file_latest", target=tipo or "download")
        elif acao in ("listar_pasta", "organizar_pasta"):
            key = _folder_key(normalize(str(params.get("pasta", ""))))
            if key is None:
                return ToolResult(
                    self.tool_id,
                    "Pasta desconhecida. Use downloads, documentos, imagens,"
                    " musicas, videos ou area de trabalho.",
                    False,
                )
            kind = "folder_list" if acao == "listar_pasta" else "organize"
            action = Action(kind, target=key)
        elif acao == "desfazer_organizacao":
            action = Action("organize_undo")
        else:
            return ToolResult(self.tool_id, f"Ação desconhecida: {acao}", False)
        outcome = run(action)
        return ToolResult(self.tool_id, outcome.message, success=outcome.ok)
