"""Ferramenta ``projetos``: o modelo consulta e anota nos projetos do usuário.

Os pedidos diretos ("o que falta no projeto X?") nem chegam ao modelo; a
ferramenta cobre o resto ("terminei a tela de login do Lumen, anota aí").
Só entra no prompt quando a mensagem fala de projeto (roteamento sob
demanda), e a descrição é curta: cada token conta.
"""

from __future__ import annotations

from typing import Any

from nicx.ferramentas._stubs import BaseTool, ToolSpec
from nicx.nucleo.registry import ToolRegistry
from nicx.nucleo.types import ToolResult

_ACOES = (
    "listar",
    "ver",
    "criar",
    "atualizar_estado",
    "decisao",
    "pendencia",
    "concluir_pendencia",
)


def _ver(projeto: Any) -> str:
    linhas = [f"Projeto {projeto.nome} (id {projeto.id})"]
    if projeto.objetivo:
        linhas.append(f"Objetivo: {projeto.objetivo}")
    linhas.append(f"Estado: {projeto.estado or '-'}")
    for decisao in projeto.decisoes[-3:]:
        linhas.append(f"Decisão ({decisao.data[:10]}): {decisao.texto}")
    for pendencia in projeto.abertas[:10]:
        linhas.append(f"Pendência: {pendencia.texto}")
    for passo in projeto.proximos_passos[:5]:
        linhas.append(f"Próximo passo: {passo}")
    if projeto.pastas:
        linhas.append(f"Pastas: {', '.join(projeto.pastas[:3])}")
    linhas.append(f"Última atividade: {projeto.ultima_atividade}")
    return "\n".join(linhas)


@ToolRegistry.register("projetos")
class ProjectsTool(BaseTool):
    """Projetos do usuário: estado, decisões e pendências (arquivo local)."""

    tool_id = "projetos"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="projetos",
            description=(
                "Projetos do usuário: listar, ver, criar, atualizar_estado,"
                " decisao, pendencia, concluir_pendencia."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": list(_ACOES)},
                    "projeto": {"type": "string", "description": "nome do projeto"},
                    "texto": {
                        "type": "string",
                        "description": "estado, decisão ou pendência",
                    },
                },
                "required": ["acao"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        from nicx.projetos import deteccao
        from nicx.projetos.armazenamento import (
            ProjetoErro,
            ProjetoJaExiste,
            Projetos,
        )

        acao = str(params.get("acao", "")).strip()
        nome = str(params.get("projeto", "") or "").strip()
        corpo = str(params.get("texto", "") or "").strip()
        if acao not in _ACOES:
            return ToolResult(self.tool_id, f"Ação desconhecida: {acao}", False)
        loja = Projetos()
        projetos = loja.listar()

        if acao == "listar":
            if not projetos:
                return ToolResult(self.tool_id, "Nenhum projeto ainda.", True)
            linhas = [
                f"- {p.nome}: {p.estado or 'sem estado'};"
                f" {len(p.abertas)} pendência(s) aberta(s)"
                for p in projetos[:15]
            ]
            return ToolResult(self.tool_id, "\n".join(linhas), True)
        if acao == "criar":
            try:
                criado = loja.criar(nome or corpo, objetivo=corpo if nome else "")
            except ProjetoJaExiste as existe:
                return ToolResult(
                    self.tool_id, f"O projeto {existe.projeto.nome} já existe.", False
                )
            except ProjetoErro:
                return ToolResult(self.tool_id, "Faltou o nome do projeto.", False)
            return ToolResult(self.tool_id, f"Projeto {criado.nome} criado.", True)

        if nome:
            projeto = loja.buscar(nome)
        else:
            projeto = deteccao.projeto_da_janela(projetos) or (
                projetos[0] if projetos else None
            )
        if projeto is None:
            nomes = ", ".join(p.nome for p in projetos[:10]) or "nenhum"
            return ToolResult(
                self.tool_id,
                f"Projeto não encontrado: {nome or '(sem nome)'}. Projetos: {nomes}.",
                False,
            )
        if acao == "ver":
            deteccao.registrar_atividade(projeto, loja=loja)
            return ToolResult(self.tool_id, _ver(projeto), True)
        if not corpo:
            return ToolResult(self.tool_id, "Faltou o texto.", False)
        try:
            if acao == "atualizar_estado":
                loja.atualizar_estado(projeto.id, corpo)
                return ToolResult(
                    self.tool_id, f"Estado de {projeto.nome} atualizado.", True
                )
            if acao == "decisao":
                loja.registrar_decisao(projeto.id, corpo)
                return ToolResult(
                    self.tool_id, f"Decisão anotada em {projeto.nome}.", True
                )
            if acao == "pendencia":
                loja.adicionar_pendencia(projeto.id, corpo)
                return ToolResult(
                    self.tool_id, f"Pendência adicionada em {projeto.nome}.", True
                )
            feita = loja.concluir_pendencia(projeto.id, corpo)
        except ProjetoErro as erro:
            return ToolResult(self.tool_id, str(erro), False)
        if feita is None:
            abertas = "; ".join(p.texto for p in projeto.abertas[:8]) or "nenhuma"
            return ToolResult(
                self.tool_id, f"Pendência não encontrada. Abertas: {abertas}.", False
            )
        return ToolResult(self.tool_id, f"Concluída: {feita.texto}.", True)


__all__ = ["ProjectsTool"]
