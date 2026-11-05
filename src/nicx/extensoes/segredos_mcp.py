"""Segredos escondidos nos argumentos e no endereço de um servidor MCP.

Exportar um pacote já tirava o ``env`` e o ``token``, mas muita gente põe a
chave direto no comando (``--api-key=...``, ``GITHUB_TOKEN=...``, ``sk-...``)
ou no endereço (``?key=...``, ``usuario:senha@``). :func:`limpar_args` e
:func:`limpar_url` deixam esses valores em branco; :func:`faltando` diz quais
ficaram em branco, para a prévia mostrar e o servidor entrar desligado até o
usuário preencher.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Nome de opção, variável ou parâmetro que guarda segredo. O nome inteiro ou
# uma parte separada por "-"/"_" ("--api-key", "GITHUB_TOKEN", "auth-token"),
# para "--author" ou "--passthrough" não caírem.
_PARTES = (
    r"api[-_]?key|apikey|key|token|secret|senha|password|passwd|auth"
    r"|bearer|credentials?|access[-_]?key|private[-_]?key|client[-_]?secret"
)
_NOME_SEGREDO = re.compile(rf"(?:^|[-_])(?:{_PARTES})(?:$|[-_])", re.IGNORECASE)
_OPCAO_COM_VALOR = re.compile(r"^(--?[A-Za-z0-9][A-Za-z0-9_.-]*)=(.*)$", re.DOTALL)
_VARIAVEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
# Valores com cara de chave, mesmo sem nome na frente.
_VALOR_SEGREDO = re.compile(
    r"^(?:sk-|sk_|pk_live_|rk_live_|ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[abprs]-"
    r"|AIza|hf_|ya29\.|eyJ[A-Za-z0-9_-]{10,}\.)[A-Za-z0-9_.\-]{8,}$"
)


# Opção que liga/desliga algo ("--no-auth", "--enable-token-cache") não
# guarda valor: o argumento seguinte não é segredo.
_LIGA_DESLIGA = re.compile(
    r"^(?:no|disable|enable|use|require|skip)[-_]", re.IGNORECASE
)


def e_nome_de_segredo(nome: str) -> bool:
    nome = nome.lstrip("-")
    return bool(_NOME_SEGREDO.search(nome)) and not _LIGA_DESLIGA.match(nome)


def limpar_args(args: list[str]) -> list[str]:
    """Os mesmos argumentos, com o valor dos segredos em branco."""
    saida: list[str] = []
    esconder_proximo = False
    for arg in map(str, args):
        if esconder_proximo:
            esconder_proximo = False
            if not arg.startswith("-"):
                saida.append("")
                continue
        opcao = _OPCAO_COM_VALOR.match(arg)
        if opcao and e_nome_de_segredo(opcao.group(1)):
            saida.append(f"{opcao.group(1)}=")
            continue
        variavel = None if arg.startswith("-") else _VARIAVEL.match(arg)
        if variavel and e_nome_de_segredo(variavel.group(1)):
            saida.append(f"{variavel.group(1)}=")
            continue
        if arg.startswith("-") and "=" not in arg and e_nome_de_segredo(arg):
            saida.append(arg)
            esconder_proximo = True
            continue
        if _VALOR_SEGREDO.match(arg):
            saida.append("")
            continue
        saida.append(arg)
    return saida


def limpar_url(url: str) -> str:
    """O endereço sem usuário/senha e com parâmetros secretos em branco."""
    if not url:
        return url
    try:
        partes = urlsplit(url)
    except ValueError:
        return ""
    netloc = partes.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    pares = parse_qsl(partes.query, keep_blank_values=True)
    mudou_query = any(e_nome_de_segredo(k) and v for k, v in pares)
    if netloc == partes.netloc and not mudou_query:
        return url
    query = (
        urlencode([(k, "" if e_nome_de_segredo(k) else v) for k, v in pares])
        if mudou_query
        else partes.query
    )
    return urlunsplit((partes.scheme, netloc, partes.path, query, partes.fragment))


def faltando(args: list[str], url: str = "") -> list[str]:
    """Nomes dos segredos que estão em branco (para o usuário preencher)."""
    nomes: list[str] = []
    args = [str(a) for a in args]
    for i, arg in enumerate(args):
        opcao = _OPCAO_COM_VALOR.match(arg)
        if opcao and e_nome_de_segredo(opcao.group(1)) and not opcao.group(2):
            nomes.append(opcao.group(1))
            continue
        variavel = None if arg.startswith("-") else _VARIAVEL.match(arg)
        if variavel and e_nome_de_segredo(variavel.group(1)) and not variavel.group(2):
            nomes.append(variavel.group(1))
            continue
        if arg == "":
            anterior = args[i - 1] if i > 0 else ""
            nomes.append(anterior if anterior.startswith("-") else f"argumento {i + 1}")
    if url:
        try:
            pares = parse_qsl(urlsplit(url).query, keep_blank_values=True)
        except ValueError:
            pares = []
        nomes.extend(k for k, v in pares if e_nome_de_segredo(k) and not v)
    return nomes


__all__ = ["e_nome_de_segredo", "faltando", "limpar_args", "limpar_url"]
