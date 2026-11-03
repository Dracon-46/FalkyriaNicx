"""Executa os pedidos de controle na janela que o usuário estava usando."""

from __future__ import annotations

import logging
import re
import sys
from typing import Callable, Optional

from nicx.acoes.intencoes import Action, normalize
from nicx.acoes.sistema import Outcome
from nicx.contexto import janela
from nicx.controle import uia
from nicx.controle.textos import texto

logger = logging.getLogger(__name__)

MAX_LISTA = 25
CONFIRMADO = 1  # ``Action.value`` da ação que o usuário já confirmou

# Botões que apagam, enviam, pagam ou desfazem trabalho: pedem "confirmo",
# mesmo quando o próprio usuário pediu (o nome achado pode ser outro).
_PERIGOSOS = re.compile(
    r"\b(?:exclu\w*|apag\w*|delet\w*|remov\w*|desinstal\w*|format\w*|envi\w*|"
    r"public\w*|compr\w*|pag\w*|transfer\w*|descart\w*|esvazi\w*|limpar tudo|"
    r"redefin\w*|restaur\w* padr\w*|resetar|"
    r"delete|remove|uninstall|send|publish|post|buy|purchase|pay|checkout|transfer|"
    r"discard|empty|erase|wipe|reset|"
    r"borrar|eliminar|enviar|comprar|pagar|"
    r"supprim\w*|effac\w*|envoy\w*|achet\w*|pai\w*|vider)\b"
)


def perigoso(nome: str) -> bool:
    return bool(_PERIGOSOS.search(normalize(nome)))


def _app(info: janela.InfoJanela) -> str:
    return janela.nome_app(info, texto("explorer"))


def _janela(
    achar_janela: Optional[Callable[[], Optional[janela.InfoJanela]]],
) -> tuple[Optional[janela.InfoJanela], Optional[Outcome]]:
    if sys.platform != "win32":
        return None, Outcome(False, texto("sem_suporte"))
    info = (achar_janela or janela.janela_de_fora)()
    if info is None:
        return None, Outcome(False, texto("sem_janela"))
    if janela.sensivel(info):
        logger.info("Janela sensível: controle recusado")
        return None, Outcome(False, texto("sensivel", app=_app(info)))
    return info, None


def _lista(nomes: list[str]) -> str:
    return ", ".join(nomes[:MAX_LISTA]) + ("…" if len(nomes) > MAX_LISTA else "")


def executar(
    action: Action,
    achar_janela: Optional[Callable[[], Optional[janela.InfoJanela]]] = None,
) -> Outcome:
    info, erro = _janela(achar_janela)
    if erro is not None:
        return erro
    app = _app(info)
    if action.op == "listar":
        elementos = uia.listar(info.hwnd)
        if elementos is None:
            return Outcome(False, texto("sem_acessibilidade", app=app))
        nomes = [e.nome for e in elementos if e.visivel and e.ativo]
        if not nomes:
            return Outcome(True, texto("lista_vazia", app=app))
        return Outcome(True, texto("lista", app=app, lista=_lista(nomes)))

    if action.op == "clicar" and action.value != CONFIRMADO:
        # pelo nome achado: "clica em tudo" pode achar "Excluir tudo"
        achado = uia.achar(info.hwnd, action.op, action.target)
        if achado is not None and perigoso(achado.nome):
            from dataclasses import replace

            from nicx.acoes import confirmacao

            confirmacao.ask(replace(action, value=CONFIRMADO))
            return Outcome(True, texto("confirmar", alvo=achado.nome, app=app))
    r = uia.agir(info.hwnd, action.op, action.target, action.site)
    nome = r.nome or action.target
    if r.estado == uia.SEM_UIA:
        return Outcome(False, texto("sem_acessibilidade", app=app))
    if r.estado == uia.DEMOROU:
        return Outcome(False, texto("demorou", app=app))
    if r.estado == uia.NAO_ACHEI:
        sugestao = (
            texto("sugestao", lista=_lista(list(r.sugestoes))) if r.sugestoes else ""
        )
        return Outcome(
            False, texto("nao_achei", alvo=action.target, app=app, sugestao=sugestao)
        )
    if r.estado == uia.DESATIVADO:
        return Outcome(False, texto("desativado", nome=nome))
    if r.estado == uia.SENHA:
        return Outcome(False, texto("senha"))
    if r.estado == uia.NAO_CLICAVEL:
        return Outcome(False, texto("nao_clicavel", nome=nome, app=app))
    if r.estado == uia.JA_ESTAVA:
        chave = "ja_marcado" if action.op == "marcar" else "ja_desmarcado"
        return Outcome(True, texto(chave, nome=nome))
    if r.estado == uia.TALVEZ:
        return Outcome(True, texto("clicado_talvez", nome=nome, app=app))
    chave = {
        "menu": "menu",
        "aba": "aba",
        "marcar": "marcado",
        "desmarcar": "desmarcado",
        "digitar": "digitado",
    }.get(action.op, "clicado")
    logger.debug("Controle: %s em um %s", action.op, r.tipo)
    return Outcome(True, texto(chave, nome=nome, app=app))


__all__ = ["CONFIRMADO", "executar", "perigoso"]
