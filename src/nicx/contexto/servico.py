"""Junta o contexto de um pedido: lê, protege e devolve o que mandar ao modelo.

``preparar`` recebe a mensagem do usuário e devolve:

- ``None`` quando não é pedido sobre a tela (ou o recurso está desligado);
- ``Preparo(resposta=...)`` quando dá para responder na hora ("onde eu tô?",
  área de transferência vazia, janela de senha...);
- ``Preparo(captura=...)`` com o texto lido; quem chama anexa o bloco no
  fim da mensagem (:func:`nicx.contexto.montagem.anexar`) já sabendo o
  espaço que sobra no ``num_ctx``.

O conteúdo nunca vai para o log: só a fonte e o tamanho, em nível debug.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Optional

from nicx.contexto import area_transferencia, janela, pedidos, selecao
from nicx.contexto.arquivo_aberto import ler_arquivo, resolver
from nicx.contexto.montagem import Captura, Leitura
from nicx.contexto.textos import texto as frase

logger = logging.getLogger(__name__)

MAX_PADRAO = 20000

# O pedido em andamento usa um modelo da nuvem? A rota do chat liga para a
# ferramenta ``contexto`` recusar (o texto da tela só vai a modelos locais).
# ``asyncio.to_thread`` copia o contexto, então vale na thread do agente.
MODELO_NA_NUVEM: ContextVar[bool] = ContextVar("nicx_contexto_nuvem", default=False)


@dataclass(frozen=True)
class Preparo:
    fonte: str
    resposta: Optional[str] = None
    captura: Optional[Captura] = None
    resto: str = ""


def config_contexto(config: Any) -> Any:
    if config is None:
        try:
            from nicx.nucleo.config import load_config

            config = load_config()
        except Exception:  # noqa: BLE001
            return None
    return getattr(config, "contexto", None)


def ativo(config: Any) -> bool:
    cfg = config_contexto(config)
    return bool(getattr(cfg, "ativo", True)) if cfg is not None else True


def max_caracteres(config: Any) -> int:
    cfg = config_contexto(config)
    try:
        valor = int(getattr(cfg, "max_caracteres", MAX_PADRAO))
    except (TypeError, ValueError):
        valor = MAX_PADRAO
    return max(1000, min(valor, 200_000))


def _app_e_detalhe(info: janela.InfoJanela, idioma: Optional[str]) -> tuple[str, str]:
    """("Visual Studio Code", ", no arquivo chat.py") / ("Edge", " (Título)")."""
    app = janela.nome_app(info, frase("explorer", idioma))
    arquivo = janela.arquivo_no_titulo(info)
    if arquivo is not None:
        return app, frase("onde_arquivo", idioma, arquivo=arquivo.nome)
    partes = janela.partes_titulo(info.titulo)
    titulo = partes[0] if partes else ""
    if titulo and titulo != app:
        return app, frase("onde_titulo", idioma, titulo=titulo[:80])
    return app, ""


def _onde(info: janela.InfoJanela, idioma: Optional[str]) -> str:
    return "".join(_app_e_detalhe(info, idioma))


def _motivo_area(leitura: Leitura, idioma: Optional[str]) -> str:
    chave = {
        area_transferencia.SEM_SUPORTE: "sem_suporte",
        area_transferencia.PROTEGIDO: "clip_protegida",
        area_transferencia.OCUPADA: "clip_ocupada",
    }.get(leitura.motivo, "clip_vazia")
    return frase(chave, idioma)


def capturar_area(max_caracteres: int, idioma: Optional[str] = None) -> Preparo:
    leitura = area_transferencia.ler(max_caracteres)
    if not leitura.ok:
        return Preparo(pedidos.AREA, resposta=_motivo_area(leitura, idioma))
    captura = Captura(
        texto=leitura.texto, fonte="area_transferencia", total=leitura.total
    )
    logger.debug("Contexto copiado: %d caracteres", leitura.total)
    return Preparo(pedidos.AREA, captura=captura)


def capturar_janela(
    max_caracteres: int,
    idioma: Optional[str] = None,
    *,
    copiar: bool = False,
    extras: tuple[str, ...] = (),
    achar_janela: Optional[Callable[[], Optional[janela.InfoJanela]]] = None,
) -> Preparo:
    """Texto da janela de fora: seleção, arquivo aberto, documento, rótulos."""
    if sys.platform != "win32":
        return Preparo(pedidos.JANELA, resposta=frase("sem_suporte", idioma))
    info = (achar_janela or janela.janela_de_fora)()
    if info is None:
        return Preparo(pedidos.JANELA, resposta=frase("sem_janela", idioma))
    app = janela.nome_app(info, frase("explorer", idioma))
    if janela.sensivel(info):
        logger.info("Janela sensível: conteúdo não lido")
        return Preparo(
            pedidos.JANELA, resposta=frase("janela_sensivel", idioma, app=app)
        )

    cabecalho = {"app": app}
    arquivo = janela.arquivo_no_titulo(info)
    if arquivo is not None:
        cabecalho["arquivo"] = arquivo.nome
    else:
        partes = janela.partes_titulo(info.titulo)
        if partes and partes[0] != app:
            cabecalho["titulo"] = partes[0]

    na_frente = janela.esta_na_frente(info)
    lido = selecao.ler_texto_da_janela(
        info.hwnd, na_frente=na_frente, max_caracteres=max_caracteres
    )
    if not lido.selecao and copiar and na_frente:
        copiado = selecao.copiar_selecao(max_caracteres)
        if copiado.strip():
            lido = selecao.TextoDaJanela(selecao=copiado)

    def pronto(texto: str, fonte: str, total: int = 0) -> Preparo:
        captura = Captura(texto, fonte, cabecalho, total or len(texto))
        logger.debug("Contexto da janela: fonte=%s, %d caracteres", fonte, len(texto))
        return Preparo(pedidos.JANELA, captura=captura)

    if lido.selecao.strip():
        return pronto(lido.selecao, "selecao")
    if arquivo is not None:
        caminho = resolver(arquivo, extras=extras)
        if caminho is not None:
            leitura = ler_arquivo(caminho, max_caracteres)
            if leitura.ok:
                cabecalho["arquivo"] = caminho.name
                return pronto(leitura.texto, "arquivo", leitura.total)
    if lido.documento.strip():
        return pronto(lido.documento, "documento")
    if lido.rotulos.strip():
        return pronto(lido.rotulos, "janela")
    return Preparo(
        pedidos.JANELA,
        resposta=frase("janela_sem_texto", idioma, onde=_onde(info, idioma)),
    )


def onde(idioma: Optional[str] = None) -> str:
    if sys.platform != "win32":
        return frase("sem_suporte", idioma)
    info = janela.janela_de_fora()
    if info is None:
        return frase("sem_janela", idioma)
    app, detalhe = _app_e_detalhe(info, idioma)
    if janela.sensivel(info):
        detalhe = ""  # nem o título de uma janela de senha/banco
    return frase("onde", idioma, app=app, detalhe=detalhe)


def preparar(
    texto: str,
    *,
    idioma: Optional[str] = None,
    config: Any = None,
    primeira: bool = True,
) -> Optional[Preparo]:
    """O contexto do pedido em *texto* (ver o docstring do módulo)."""
    if not ativo(config):
        return None
    pedido = pedidos.detectar(texto, primeira=primeira)
    if pedido is None:
        return None
    if pedido.fonte == pedidos.ONDE:
        return Preparo(pedidos.ONDE, resposta=onde(idioma))
    maximo = max_caracteres(config)
    if pedido.fonte == pedidos.AREA:
        preparo = capturar_area(maximo, idioma)
    else:
        cfg = config_contexto(config)
        preparo = capturar_janela(
            maximo,
            idioma,
            copiar=bool(getattr(cfg, "copiar_selecao", False)),
            extras=tuple(getattr(cfg, "pastas_extras", None) or ()),
        )
    return Preparo(preparo.fonte, preparo.resposta, preparo.captura, pedido.resto)


__all__ = [
    "Preparo",
    "ativo",
    "capturar_area",
    "capturar_janela",
    "onde",
    "preparar",
]
