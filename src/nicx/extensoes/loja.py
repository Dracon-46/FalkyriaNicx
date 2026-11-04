"""Loja de pacotes da Falkyria (Supabase do projeto ``nicx``).

O app só lê: o catálogo publicado (``nicx_loja_pacotes``) e a versão assinada
(``nicx_loja_versoes``). Antes de mostrar a prévia ou instalar, confere a
impressão digital e a assinatura (:mod:`nicx.extensoes.assinatura`); daí em
diante é o mesmo caminho dos pacotes por arquivo (:mod:`nicx.extensoes.pacotes`).

Nada identifica quem navega ou baixa: o pedido leva só a chave pública do app
e o contador de downloads só soma (``nicx_loja_baixou``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

PRAZO_S = 15.0
_CAMPOS = "id,nome,descricao,autor,categoria,versao,downloads,atualizado_em"


class LojaErro(RuntimeError):
    """A loja não respondeu ou o pacote não passou na conferência."""


def _destino() -> tuple[str, str]:
    from nicx.nucleo.config import AnalyticsConfig

    padrao = AnalyticsConfig()
    try:
        from nicx.nucleo.config import load_config

        cfg = load_config().analytics
        return (cfg.host or padrao.host).rstrip("/"), cfg.key or padrao.key
    except Exception:  # noqa: BLE001
        return padrao.host.rstrip("/"), padrao.key


def _cabecalhos(chave: str) -> dict[str, str]:
    from nicx.privacidade.supabase_sink import _headers

    return _headers(chave)


def _get(caminho: str, params: dict[str, str]) -> list[dict[str, Any]]:
    import httpx

    host, chave = _destino()
    try:
        resposta = httpx.get(
            f"{host}/rest/v1/{caminho}",
            params=params,
            headers=_cabecalhos(chave),
            timeout=PRAZO_S,
        )
    except httpx.HTTPError as exc:
        raise LojaErro("sem conexão com a loja") from exc
    if resposta.status_code == 404:
        raise LojaErro("a loja ainda não está no ar")
    if resposta.status_code >= 400:
        raise LojaErro(f"a loja respondeu {resposta.status_code}")
    dados = resposta.json()
    return [d for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []


def catalogo() -> list[dict[str, Any]]:
    """Os pacotes publicados, com o que já está instalado e se há atualização."""
    from nicx.extensoes import pacotes

    itens = _get(
        "nicx_loja_pacotes",
        {"select": _CAMPOS, "publicado": "eq.true", "order": "nome.asc"},
    )
    instalados = {p.get("id"): p for p in pacotes.instalados() if p.get("loja")}
    for item in itens:
        local = instalados.get(item.get("id"))
        item["versao_instalada"] = (local or {}).get("versao", "")
        item["atualizacao"] = bool(local) and local.get("versao") != item.get("versao")
    return itens


def baixar(pacote_id: str, versao: Optional[str] = None) -> dict[str, Any]:
    """O pacote conferido (assinatura e impressão), pronto para prévia ou instalação."""
    from nicx.extensoes import assinatura, pacotes

    if versao is None:
        achados = _get(
            "nicx_loja_pacotes",
            {"select": "versao", "id": f"eq.{pacote_id}", "publicado": "eq.true"},
        )
        if not achados:
            raise LojaErro("pacote não encontrado na loja")
        versao = str(achados[0].get("versao", ""))
    linhas = _get(
        "nicx_loja_versoes",
        {
            "select": "conteudo,sha256,assinatura,chave",
            "pacote_id": f"eq.{pacote_id}",
            "versao": f"eq.{versao}",
        },
    )
    if not linhas:
        raise LojaErro("versão não encontrada na loja")
    linha = linhas[0]
    conteudo = str(linha.get("conteudo", ""))
    try:
        assinatura.verificar(
            conteudo,
            str(linha.get("sha256", "")),
            str(linha.get("assinatura", "")),
            str(linha.get("chave", "")),
        )
        pacote = pacotes.ler(conteudo)
    except (assinatura.AssinaturaInvalida, pacotes.PacoteInvalido) as exc:
        logger.warning("Pacote %s da loja recusado: %s", pacote_id, exc)
        raise LojaErro(f"pacote recusado: {exc}") from exc
    if pacote["id"] != pacote_id or str(pacote.get("versao", "")) != versao:
        raise LojaErro("pacote recusado: o conteúdo não é o anunciado")
    return pacote


def previa(pacote_id: str) -> dict[str, Any]:
    from nicx.extensoes import pacotes

    return {**pacotes.previa(baixar(pacote_id)), "loja": True, "verificado": True}


def _contar(pacote_id: str) -> None:
    import httpx

    host, chave = _destino()
    try:
        httpx.post(
            f"{host}/rest/v1/rpc/nicx_loja_baixou",
            json={"p_id": pacote_id},
            headers=_cabecalhos(chave),
            timeout=PRAZO_S,
        )
    except httpx.HTTPError:
        logger.debug("Contador da loja não respondeu", exc_info=True)


def instalar(pacote_id: str, *, com_mcp: bool = False) -> dict[str, Any]:
    from nicx.extensoes import pacotes

    resultado = pacotes.instalar(baixar(pacote_id), com_mcp=com_mcp, loja=True)
    _contar(pacote_id)
    return resultado


__all__ = ["LojaErro", "baixar", "catalogo", "instalar", "previa"]
