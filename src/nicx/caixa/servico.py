"""Monta a caixa de entrada a partir das fontes que já existem.

Cada item tem um ``id`` estável que inclui o estado (``trabalho:<id>:concluida``):
dispensar um aviso esconde só aquele acontecimento; se a mesma tarefa falhar
de novo depois, o aviso novo aparece. Decisões (aprovar, responder, aprovar
plano) não se dispensam: somem quando a pessoa decide.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

DECISAO = "decisao"
AVISO = "aviso"

#: Avisos mais velhos que isso saem da caixa sozinhos.
VALIDADE_AVISO = timedelta(days=7)
MAX_VISTOS = 500

_LOCK = threading.Lock()


def _arquivo_vistos() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "caixa_vistos.json"


def _ler_vistos() -> list[str]:
    try:
        dados = json.loads(_arquivo_vistos().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return (
        [str(x) for x in dados if isinstance(x, str)] if isinstance(dados, list) else []
    )


def _gravar_vistos(vistos: list[str]) -> None:
    p = _arquivo_vistos()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(vistos[-MAX_VISTOS:]), encoding="utf-8")
    tmp.replace(p)


def _quando(valor: Any) -> Optional[datetime]:
    """ISO ou epoch → datetime com fuso (UTC quando vier sem)."""
    if valor in (None, ""):
        return None
    try:
        if isinstance(valor, (int, float)):
            d = datetime.fromtimestamp(float(valor), tz=timezone.utc)
        else:
            d = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError, OSError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: Optional[datetime]) -> str:
    return d.isoformat(timespec="seconds") if d else ""


def _item(
    id_: str,
    tipo: str,
    categoria: str,
    quando: Optional[datetime],
    *,
    titulo: str = "",
    texto: str = "",
    ref: str = "",
    link: str = "",
    extra: Optional[dict] = None,
) -> dict:
    return {
        "id": id_,
        "tipo": tipo,
        "categoria": categoria,
        "quando": _iso(quando),
        "titulo": titulo[:300],
        "texto": texto[:1000],
        "ref": ref,
        "link": link,
        "extra": extra or {},
    }


# ----------------------------------------------------------------- fontes


def _de_aprovacoes(store: Any) -> list[dict]:
    if store is None:
        return []
    try:
        store.expire_stale()
        pendentes = store.list_pending()
    except Exception:  # noqa: BLE001
        logger.debug("Aprovações indisponíveis para a caixa", exc_info=True)
        return []
    itens = []
    for a in pendentes:
        itens.append(
            _item(
                f"aprovacao:{a.id}",
                "aprovacao",
                DECISAO,
                _quando(a.created_at),
                titulo=a.action_type,
                texto=a.description,
                ref=a.id,
                extra={"tier": a.tier, "payload": a.payload},
            )
        )
    return itens


def _de_trabalho() -> tuple[list[dict], bool]:
    """Itens do modo Trabalho e se há tarefa trabalhando agora."""
    try:
        from nicx.trabalho import modelo, servico
    except Exception:  # noqa: BLE001
        return [], False
    try:
        tarefas = servico.listar()
    except Exception:  # noqa: BLE001
        logger.debug("Tarefas indisponíveis para a caixa", exc_info=True)
        return [], False
    itens: list[dict] = []
    trabalhando = False
    for t in tarefas:
        estado = t.get("estado", "")
        tid = str(t.get("id", ""))
        quando = _quando(t.get("atualizado_em")) or _quando(t.get("criado_em"))
        base = {"titulo": t.get("pedido", ""), "ref": tid, "link": "/trabalho"}
        if estado in (modelo.PLANEJANDO, modelo.EXECUTANDO):
            trabalhando = True
        if estado == modelo.AGUARDANDO_CONFIRMACAO and t.get("pergunta"):
            trabalhando = True
            itens.append(
                _item(
                    f"trabalho:{tid}:pergunta",
                    "trabalho_pergunta",
                    DECISAO,
                    quando,
                    texto=str((t.get("pergunta") or {}).get("texto", "")),
                    **base,
                )
            )
        elif estado == modelo.AGUARDANDO_APROVACAO:
            passos = [p.get("descricao", "") for p in t.get("plano", [])]
            itens.append(
                _item(
                    f"trabalho:{tid}:plano",
                    "trabalho_plano",
                    DECISAO,
                    quando,
                    texto="\n".join(passos[:7]),
                    extra={"passos": len(passos)},
                    **base,
                )
            )
        elif estado == modelo.CONCLUIDA:
            itens.append(
                _item(
                    f"trabalho:{tid}:concluida",
                    "trabalho_concluida",
                    AVISO,
                    quando,
                    texto=t.get("resumo", ""),
                    extra={"arquivos": len(t.get("arquivos_mudados", []))},
                    **base,
                )
            )
        elif estado == modelo.ERRO:
            itens.append(
                _item(
                    f"trabalho:{tid}:erro",
                    "trabalho_erro",
                    AVISO,
                    quando,
                    texto=t.get("erro", ""),
                    **base,
                )
            )
        elif estado == modelo.INTERROMPIDA:
            itens.append(
                _item(
                    f"trabalho:{tid}:interrompida",
                    "trabalho_interrompida",
                    AVISO,
                    quando,
                    **base,
                )
            )
    return itens, trabalhando


_AGENTE_TIPOS = {
    "error": "agente_erro",
    "needs_attention": "agente_atencao",
    "budget_exceeded": "agente_orcamento",
}


def _de_agentes(manager: Any) -> tuple[list[dict], bool]:
    if manager is None:
        return [], False
    try:
        agentes = manager.list_agents()
    except Exception:  # noqa: BLE001
        logger.debug("Agentes indisponíveis para a caixa", exc_info=True)
        return [], False
    itens = []
    rodando = False
    for a in agentes:
        status = a.get("status", "")
        if status == "running":
            rodando = True
        tipo = _AGENTE_TIPOS.get(status)
        if not tipo:
            continue
        quando = _quando(a.get("updated_at"))
        marca = int(a.get("updated_at") or 0)
        itens.append(
            _item(
                f"agente:{a.get('id')}:{status}:{marca}",
                tipo,
                AVISO,
                quando,
                titulo=a.get("name", ""),
                texto=a.get("current_activity", "")
                or a.get("summary_memory", "")[:300],
                ref=str(a.get("id", "")),
                link="/agents",
            )
        )
    return itens, rodando


# ------------------------------------------------------------------ montar


def montar(
    *,
    aprovacoes: Any = None,
    agentes: Any = None,
    agora: Optional[datetime] = None,
) -> dict:
    """A caixa inteira: decisões primeiro (mais antigas antes), depois avisos."""
    agora = agora or datetime.now(timezone.utc)
    vistos = set(_ler_vistos())
    itens_trab, trabalhando = _de_trabalho()
    itens_ag, rodando = _de_agentes(agentes)
    todos = _de_aprovacoes(aprovacoes) + itens_trab + itens_ag

    decisoes = sorted(
        (i for i in todos if i["categoria"] == DECISAO), key=lambda i: i["quando"]
    )
    avisos = []
    for i in todos:
        if i["categoria"] != AVISO or i["id"] in vistos:
            continue
        q = _quando(i["quando"])
        if q and agora - q > VALIDADE_AVISO:
            continue
        avisos.append(i)
    avisos.sort(key=lambda i: i["quando"], reverse=True)

    ultimo_concluido = max(
        (i["quando"] for i in avisos if i["tipo"] == "trabalho_concluida"), default=""
    )
    ultimo_erro = max(
        (
            i["quando"]
            for i in avisos
            if i["tipo"] in ("trabalho_erro", "agente_erro", "agente_orcamento")
        ),
        default="",
    )
    return {
        "decisoes": decisoes,
        "avisos": avisos,
        "atividade": {
            "trabalhando": trabalhando or rodando,
            "esperando": len(decisoes),
            "ultimo_concluido": ultimo_concluido,
            "ultimo_erro": ultimo_erro,
        },
    }


def dispensar(ids: Iterable[str]) -> int:
    """Esconde avisos (decisões não se dispensam). Devolve quantos entraram."""
    novos = [str(i) for i in ids if i and not str(i).startswith(("aprovacao:",))]
    novos = [i for i in novos if not i.endswith((":pergunta", ":plano"))]
    if not novos:
        return 0
    with _LOCK:
        vistos = _ler_vistos()
        atuais = set(vistos)
        acrescentados = [i for i in dict.fromkeys(novos) if i not in atuais]
        if acrescentados:
            _gravar_vistos(vistos + acrescentados)
    return len(acrescentados)


def dispensar_avisos(*, aprovacoes: Any = None, agentes: Any = None) -> int:
    """Esconde todos os avisos que estão na caixa agora."""
    caixa = montar(aprovacoes=aprovacoes, agentes=agentes)
    return dispensar(i["id"] for i in caixa["avisos"])


__all__ = ["AVISO", "DECISAO", "dispensar", "dispensar_avisos", "montar"]
