"""O arquivo de versões ``nicx-atualizacao.json``, assinado pela Falkyria.

Vai em cada release, ao lado do ``NicxSetup.exe``. O conteúdo assinado (JSON
canônico, :func:`nicx.extensoes.assinatura.canonico`) diz a versão, o
endereço e o sha256 do instalador, o comando do Mac e as novidades. O campo
``tipo`` separa este arquivo dos pacotes da loja, assinados pela mesma chave:
um não passa pelo outro.

Gerar (no PC da Falkyria, com a chave em ``~/.falkyria-loja/``)::

    nicx atualizacao assinar packaging/windows/dist/NicxSetup.exe --versao 0.2.1
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from nicx.extensoes import assinatura

TIPO = "nicx-atualizacao"
FORMATO = 1
NOME_ARQUIVO = "nicx-atualizacao.json"
REPOSITORIO = "https://github.com/Dracon-46/FalkyriaNicx"
URL_PADRAO = f"{REPOSITORIO}/releases/latest/download/{NOME_ARQUIVO}"
# O instalador só pode vir das releases do Nicx (e ainda tem que bater com o
# sha256 assinado).
PREFIXO_DOWNLOAD = f"{REPOSITORIO}/releases/download/"
COMANDO_MAC = (
    "curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/"
    "scripts/install/install.sh | bash"
)
MAX_INSTALADOR = 500 * 1024 * 1024
_VERSAO = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class ManifestoInvalido(ValueError):
    """O arquivo de versões não serve; a mensagem diz por quê."""


def versao_tupla(texto: str) -> Optional[tuple[int, int, int]]:
    """``"0.2.1"`` → ``(0, 2, 1)``; versões de desenvolvimento contam pela base."""
    m = _VERSAO.match((texto or "").strip().lstrip("v"))
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def mais_nova(candidata: str, atual: str) -> bool:
    nova, velha = versao_tupla(candidata), versao_tupla(atual)
    return bool(nova and velha and nova > velha)


def sha256_do_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with Path(caminho).open("rb") as arq:
        for bloco in iter(lambda: arq.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def montar(
    versao: str,
    instalador: Path,
    *,
    novidades: Optional[list[dict]] = None,
    publicado_em: Optional[str] = None,
) -> dict[str, Any]:
    """O conteúdo (ainda sem assinatura) do arquivo de versões."""
    from nicx.atualizacao.novidades import NOVIDADES

    if versao_tupla(versao) is None:
        raise ManifestoInvalido("versão no formato 0.2.1")
    instalador = Path(instalador)
    lista = NOVIDADES if novidades is None else novidades
    return {
        "tipo": TIPO,
        "formato_atualizacao": FORMATO,
        "versao": versao,
        "publicado_em": publicado_em or date.today().isoformat(),
        "windows": {
            "arquivo": instalador.name,
            "url": f"{PREFIXO_DOWNLOAD}v{versao}/{instalador.name}",
            "sha256": sha256_do_arquivo(instalador),
            "tamanho": instalador.stat().st_size,
        },
        "mac": {"comando": COMANDO_MAC},
        "novidades": lista[:20],
    }


def assinar(conteudo: dict[str, Any], pasta_chave: Optional[Path] = None) -> dict:
    return assinatura.assinar(conteudo, pasta_chave)


def ler(dados: Any, confiaveis: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """Confere a assinatura e o formato; devolve o conteúdo assinado."""
    if not isinstance(dados, dict):
        raise ManifestoInvalido("o arquivo de versões veio estragado")
    try:
        assinatura.verificar(
            str(dados["conteudo"]),
            str(dados["sha256"]),
            str(dados["assinatura"]),
            str(dados["chave"]),
            confiaveis,
        )
        conteudo = json.loads(dados["conteudo"])
    except KeyError as exc:
        raise ManifestoInvalido("o arquivo de versões veio incompleto") from exc
    except assinatura.AssinaturaInvalida as exc:
        raise ManifestoInvalido(
            f"a assinatura da Falkyria não confere ({exc})"
        ) from exc
    except ValueError as exc:
        raise ManifestoInvalido("o arquivo de versões veio estragado") from exc
    if not isinstance(conteudo, dict) or conteudo.get("tipo") != TIPO:
        raise ManifestoInvalido("não é um arquivo de versões do Nicx")
    if conteudo.get("formato_atualizacao") != FORMATO:
        raise ManifestoInvalido("formato de arquivo de versões que este Nicx não lê")
    if versao_tupla(str(conteudo.get("versao", ""))) is None:
        raise ManifestoInvalido("versão inválida no arquivo de versões")
    win = conteudo.get("windows")
    if win is not None:
        if (
            not isinstance(win, dict)
            or not str(win.get("url", "")).startswith(PREFIXO_DOWNLOAD)
            or not _SHA.match(str(win.get("sha256", "")))
            or not isinstance(win.get("tamanho"), int)
            or not 0 < win["tamanho"] <= MAX_INSTALADOR
            or not re.match(r"^[A-Za-z0-9._-]+\.exe$", str(win.get("arquivo", "")))
        ):
            raise ManifestoInvalido(
                "instalador do Windows inválido no arquivo de versões"
            )
    if not isinstance(conteudo.get("novidades", []), list):
        raise ManifestoInvalido("novidades inválidas no arquivo de versões")
    return conteudo


__all__ = [
    "COMANDO_MAC",
    "ManifestoInvalido",
    "NOME_ARQUIVO",
    "PREFIXO_DOWNLOAD",
    "TIPO",
    "URL_PADRAO",
    "assinar",
    "ler",
    "mais_nova",
    "montar",
    "sha256_do_arquivo",
    "versao_tupla",
]
