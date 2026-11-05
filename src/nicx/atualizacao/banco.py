"""Novidades no Supabase da Falkyria (tabela ``nicx_novidades``).

A Falkyria cadastra as novidades pelo Painel (seção Novidades) ou com um
INSERT. :func:`buscar` lê as publicadas com a chave pública (a regra de linha
só deixa o visitante ver ``publicado = true``) para ``nicx atualizacao
assinar`` pôr no arquivo de versões da release. O app em si não consulta a
tabela: mostra o que veio assinado.
"""

from __future__ import annotations

from typing import Any, Optional

from nicx.atualizacao.manifesto import versao_tupla

TABELA = "nicx_novidades"


class NovidadesIndisponiveis(RuntimeError):
    """Não deu para ler as novidades do banco; a mensagem diz por quê."""


def _destino(config: Any = None) -> tuple[str, str]:
    if config is None:
        from nicx.nucleo.config import load_config

        config = load_config()
    analytics = config.analytics
    host = (analytics.host or "").rstrip("/")
    if not host or not analytics.key:
        raise NovidadesIndisponiveis("sem o endereço do Supabase da Falkyria na config")
    return host, analytics.key


def _limpar(linha: dict[str, Any]) -> Optional[dict[str, Any]]:
    versao = str(linha.get("versao", ""))
    itens = linha.get("itens")
    if versao_tupla(versao) is None or not isinstance(itens, list):
        return None
    return {
        "versao": versao,
        "data": str(linha.get("data", "")),
        "titulo": str(linha.get("titulo", "")),
        "itens": [str(i) for i in itens if str(i).strip()],
    }


def buscar(config: Any = None, *, cliente: Any = None) -> list[dict[str, Any]]:
    """As novidades publicadas, da versão mais nova para a mais antiga."""
    import httpx

    host, chave = _destino(config)
    dono = cliente or httpx.Client(timeout=20.0)
    try:
        resp = dono.get(
            f"{host}/rest/v1/{TABELA}",
            params={"select": "versao,data,titulo,itens", "publicado": "eq.true"},
            headers={"apikey": chave, "Authorization": f"Bearer {chave}"},
        )
        resp.raise_for_status()
        linhas = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise NovidadesIndisponiveis(
            f"não consegui ler as novidades do banco ({exc})"
        ) from exc
    finally:
        if cliente is None:
            dono.close()
    if not isinstance(linhas, list):
        raise NovidadesIndisponiveis("o banco respondeu algo inesperado")
    limpas = [n for n in (_limpar(x) for x in linhas if isinstance(x, dict)) if n]
    return sorted(limpas, key=lambda n: versao_tupla(n["versao"]), reverse=True)


__all__ = ["NovidadesIndisponiveis", "TABELA", "buscar"]
