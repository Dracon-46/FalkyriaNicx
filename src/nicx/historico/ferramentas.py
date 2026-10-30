"""Autonomia, cópia para desfazer e histórico das ferramentas do modelo.

Chamado pelo ``ToolExecutor`` (``nicx.ferramentas._stubs``), o ponto por onde
passa toda ferramenta. Nada aqui levanta: um problema no histórico não pode
impedir a ferramenta de rodar.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from nicx.historico import autonomia, textos
from nicx.historico.registro import BLOQUEADO, FALHOU, OK, PENDENTE, anotar

logger = logging.getLogger(__name__)

_ESCREVEM_ARQUIVO = frozenset({"file_write", "apply_patch"})
_CAMINHOS_PATCH = re.compile(
    r"^(?:\*\*\* (?:Update|Add|Delete) File: |\+\+\+ b/|--- a/)(?P<p>.+?)\s*$", re.M
)


def resumo(nome: str, params: Mapping[str, Any]) -> str:
    """Uma linha curta sobre a chamada (para o histórico e para a confirmação)."""
    for chave in (
        "path",
        "command",
        "query",
        "url",
        "acao",
        "action",
        "name",
        "nome",
        "text",
        "texto",
    ):
        valor = params.get(chave)
        if valor:
            return _curto(str(valor), 120)
    if nome == "apply_patch":
        caminhos = _caminhos_patch(str(params.get("patch", "")))
        return ", ".join(str(c) for c in caminhos[:3]) or "patch"
    partes = [f"{k}={_curto(str(v), 40)}" for k, v in list(params.items())[:2]]
    return ", ".join(partes) or nome


def _curto(texto: str, n: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def _caminhos_patch(patch: str) -> list[Path]:
    vistos: list[Path] = []
    for m in _CAMINHOS_PATCH.finditer(patch):
        bruto = m.group("p").strip()
        if bruto in {"/dev/null", ""}:
            continue
        caminho = Path(bruto)
        if not caminho.is_absolute():
            caminho = Path(os.getcwd()) / caminho
        if caminho not in vistos:
            vistos.append(caminho)
    return vistos


def copia_antes(nome: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Antes de escrever arquivos: guarda como desfazer (cópia ou "era novo")."""
    if nome not in _ESCREVEM_ARQUIVO:
        return []
    try:
        from nicx.historico.desfazer import guardar_copia

        if nome == "file_write":
            alvos = (
                [Path(str(params.get("path", ""))).expanduser()]
                if params.get("path")
                else []
            )
        else:
            alvos = _caminhos_patch(str(params.get("patch", "")))
        planos = []
        for alvo in alvos[:20]:
            if alvo.exists():
                copia = guardar_copia(alvo, "arquivo-")
                if copia is not None:
                    planos.append(
                        {"tipo": "arquivo", "caminho": str(alvo), "copia": str(copia)}
                    )
            else:
                planos.append({"tipo": "arquivo", "caminho": str(alvo), "novo": True})
        return planos
    except Exception:  # noqa: BLE001
        logger.debug("Sem cópia para desfazer", exc_info=True)
        return []


def anotar_chamada(
    nome: str,
    params: Mapping[str, Any],
    sucesso: bool,
    conteudo: str,
    *,
    nivel: str,
    planos: Optional[list[dict[str, Any]]] = None,
    resultado: Optional[str] = None,
) -> None:
    """Uma linha na auditoria; escrever arquivo também vira linha desfazível."""
    try:
        args = {
            k: _curto(json.dumps(v, ensure_ascii=False, default=str), 300)
            for k, v in params.items()
        }
        anotar(
            "ferramenta",
            textos.texto("ferramenta", ferramenta=nome, resumo=resumo(nome, params)),
            detalhe={
                "ferramenta": nome,
                "argumentos": args,
                "resposta": _curto(conteudo or "", 400),
                "risco": risco(nome, params),
            },
            resultado=resultado or (OK if sucesso else FALHOU),
            nivel=nivel,
        )
        if sucesso and planos:
            for plano in planos:
                chave = "arquivo_criado" if plano.get("novo") else "arquivo_alterado"
                anotar(
                    "arquivo",
                    textos.texto(chave, caminho=plano["caminho"]),
                    detalhe={"ferramenta": nome, "caminho": plano["caminho"]},
                    nivel=nivel,
                    desfazer=plano,
                )
    except Exception:  # noqa: BLE001
        logger.debug("Chamada de ferramenta não anotada", exc_info=True)


def risco(nome: str, params: Mapping[str, Any], pede_confirmacao: bool = False) -> str:
    return autonomia.risco_ferramenta(nome, params, pede_confirmacao=pede_confirmacao)


def portao(
    nome: str,
    params: Mapping[str, Any],
    *,
    pede_confirmacao: bool,
    interativo: bool,
    confirmar: Optional[Callable[[str], bool]],
    executar: Callable[[], Any],
    fazer_resultado: Callable[[str, bool, dict[str, Any]], Any],
) -> Optional[Any]:
    """Decide se a chamada segue. Devolve um ToolResult para parar, ou None para seguir.

    ``executar`` roda a ferramenta de verdade (usado quando o usuário diz
    "confirmo" depois); ``fazer_resultado(texto, sucesso, metadata)`` monta o
    ToolResult no formato do executor.
    """
    if nome in autonomia.DELEGADAS:
        return None  # a regra vale dentro de nicx.acoes.sistema.run
    r = risco(nome, params, pede_confirmacao)
    nivel = autonomia.nivel_atual()
    if not autonomia.precisa_confirmar(r, nivel):
        return None
    descricao = resumo(nome, params)
    if interativo and confirmar is not None:
        if confirmar(f"[{nivel}] {nome}: {descricao}?"):
            return None
        anotar_chamada(
            nome, params, False, "negado pelo usuário", nivel=nivel, resultado=BLOQUEADO
        )
        return fazer_resultado(
            f"Tool '{nome}' execution denied by user.", False, {"negado": True}
        )

    from nicx.acoes import confirmacao
    from nicx.acoes.intencoes import Action

    def depois_do_confirmo() -> str:
        try:
            res = executar()
        except Exception as exc:  # noqa: BLE001 - vira frase
            return textos.texto(
                "ferramenta_falhou", ferramenta=nome, resultado=str(exc)
            )
        chave = (
            "ferramenta_feita"
            if getattr(res, "success", False)
            else "ferramenta_falhou"
        )
        return textos.texto(
            chave,
            ferramenta=nome,
            resultado=_curto(str(getattr(res, "content", "")), 300),
        )

    confirmacao.ask(
        Action("tool", target=f"{nome}: {descricao}"),
        window=confirmacao.TOOL_WINDOW_SECONDS,
        fn=depois_do_confirmo,
    )
    anotar_chamada(
        nome, params, False, "aguardando confirmação", nivel=nivel, resultado=PENDENTE
    )
    frase = textos.texto(
        "ferramenta_pendente",
        ferramenta=nome,
        resumo=descricao,
        nivel=textos.texto(f"nivel_{nivel}"),
    )
    return fazer_resultado(
        frase, False, {"aguardando_confirmacao": True, "nivel": nivel}
    )


__all__ = ["anotar_chamada", "copia_antes", "portao", "resumo"]
