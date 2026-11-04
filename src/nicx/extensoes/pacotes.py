"""Pacotes: assistentes, rotinas, habilidades e servidores MCP que vêm juntos.

Um pacote é um JSON (``formato: 1``) com ``id``, ``nome``, ``descricao``,
``versao``, ``autor`` e as listas ``assistentes``, ``rotinas``, ``habilidades``
e ``mcp``. Os prontos por profissão estão em :mod:`pacotes_prontos`; outros
chegam por arquivo (exportados por alguém).

Antes de instalar, :func:`previa` diz o que entra e o que o pacote pode fazer
(:func:`permissoes`): comandos que rodam no PC, endereços na internet,
ferramentas dos assistentes, segredos que pede. Servidores MCP só entram se o
usuário marcar, e entram desligados quando faltam segredos.

A instalação fica registrada em ``~/.nicx/pacotes.json`` com os ids de tudo que
entrou, para :func:`desinstalar` tirar o pacote inteiro. Exportar
(:func:`exportar`) nunca leva token nem valor de variável de ambiente.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

FORMATO = 1
MAX_BYTES = 1024 * 1024
MAX_ITENS = 50
_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
_LOCK = threading.RLock()
_LISTAS = ("assistentes", "rotinas", "habilidades", "mcp")


class PacoteInvalido(ValueError):
    """Pacote que não dá para instalar; a mensagem diz por quê."""


# ------------------------------------------------------------------ leitura
def ler(texto: str | bytes) -> dict[str, Any]:
    """Valida o formato geral e devolve o pacote (sem instalar nada)."""
    if len(texto) > MAX_BYTES:
        raise PacoteInvalido("o pacote passa de 1 MB")
    try:
        dados = json.loads(texto)
    except ValueError as exc:
        raise PacoteInvalido("o arquivo não é um pacote do Nicx (JSON)") from exc
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
        raise PacoteInvalido("o arquivo não é um pacote do Nicx (formato 1)")
    if not _ID.match(str(dados.get("id", ""))):
        raise PacoteInvalido("id do pacote: letras minúsculas, números e hífen")
    if not str(dados.get("nome", "")).strip():
        raise PacoteInvalido("o pacote precisa de um nome")
    for lista in _LISTAS:
        valor = dados.get(lista) or []
        if not isinstance(valor, list) or not all(isinstance(i, dict) for i in valor):
            raise PacoteInvalido(f"{lista}: precisa ser uma lista")
        if len(valor) > MAX_ITENS:
            raise PacoteInvalido(f"{lista}: itens demais")
        dados[lista] = valor
    dados["nome"] = " ".join(str(dados["nome"]).split())[:60]
    dados["descricao"] = " ".join(str(dados.get("descricao", "")).split())[:300]
    dados["versao"] = str(dados.get("versao", ""))[:20]
    dados["autor"] = " ".join(str(dados.get("autor", "")).split())[:60]
    return dados


def permissoes(pacote: dict[str, Any]) -> dict[str, Any]:
    """O que o pacote pode fazer no PC, para o usuário ver antes de instalar."""
    comandos, enderecos, segredos = [], [], []
    for s in pacote.get("mcp", []):
        if s.get("url"):
            enderecos.append(str(s["url"]))
        else:
            comandos.append(
                " ".join([str(s.get("comando", "")), *map(str, s.get("args", []))])
            )
        segredos.extend(str(k) for k in (s.get("env") or {}))
        if s.get("token") is not None and s.get("url"):
            segredos.append(f"token ({s.get('nome', '')})")
    ferramentas: set[str] = set()
    for a in pacote.get("assistentes", []):
        ferramentas |= {str(f) for f in a.get("ferramentas") or []}
    agendadas, sites = [], []
    for r in pacote.get("rotinas", []):
        if r.get("agenda"):
            agendadas.append(str(r.get("nome", "")))
        for p in r.get("passos") or []:
            if isinstance(p, dict) and p.get("kind") == "open_url":
                sites.append(str(p.get("target", "")))
    return {
        "comandos": comandos,
        "enderecos": enderecos + sites,
        "segredos": segredos,
        "ferramentas": sorted(ferramentas),
        "todas_as_ferramentas": "*" in ferramentas,
        "rotinas_com_horario": agendadas,
    }


def _problemas(pacote: dict[str, Any]) -> list[str]:
    """Itens que não passariam na validação de cada tipo."""
    from nicx.assistentes.modelo import Assistente
    from nicx.assistentes.modelo import validar as validar_assistente
    from nicx.extensoes import mcp
    from nicx.rotinas.modelo import Rotina
    from nicx.rotinas.modelo import validar as validar_rotina

    problemas = []
    for a in pacote["assistentes"]:
        try:
            validar_assistente(Assistente.de_dict(a))
        except ValueError as exc:
            problemas.append(f"assistente {a.get('nome', '?')}: {exc}")
    for r in pacote["rotinas"]:
        try:
            validar_rotina(Rotina.de_dict(r))
        except ValueError as exc:
            problemas.append(f"rotina {r.get('nome', '?')}: {exc}")
    for h in pacote["habilidades"]:
        if not h.get("instrucoes") or not h.get("descricao"):
            problemas.append(
                f"habilidade {h.get('nome', '?')}: faltam descrição ou instruções"
            )
    for s in pacote["mcp"]:
        try:
            mcp.validar(mcp.Servidor.de_dict(s))
        except ValueError as exc:
            problemas.append(f"servidor {s.get('nome', '?')}: {exc}")
    return problemas


def previa(pacote: dict[str, Any]) -> dict[str, Any]:
    instalado = obter_instalado(pacote["id"])
    return {
        "id": pacote["id"],
        "nome": pacote["nome"],
        "descricao": pacote.get("descricao", ""),
        "versao": pacote.get("versao", ""),
        "autor": pacote.get("autor", ""),
        "pronto": bool(pacote.get("pronto")),
        "itens": {
            "assistentes": [a.get("nome", "") for a in pacote["assistentes"]],
            "rotinas": [r.get("nome", "") for r in pacote["rotinas"]],
            "habilidades": [
                h.get("titulo") or h.get("nome", "") for h in pacote["habilidades"]
            ],
            "mcp": [s.get("nome", "") for s in pacote["mcp"]],
        },
        "permissoes": permissoes(pacote),
        "problemas": _problemas(pacote),
        "instalado": instalado is not None,
        "versao_instalada": (instalado or {}).get("versao", ""),
    }


# -------------------------------------------------------------- registro local
def _caminho() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "pacotes.json"


def instalados() -> list[dict[str, Any]]:
    try:
        dados = json.loads(_caminho().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [d for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []


def obter_instalado(pacote_id: str) -> Optional[dict[str, Any]]:
    return next((p for p in instalados() if p.get("id") == pacote_id), None)


def _gravar(lista: list[dict[str, Any]]) -> None:
    arquivo = _caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, arquivo)


def _anotar(titulo: str) -> None:
    from nicx.historico.registro import anotar

    anotar("extensao", titulo, detalhe={"tipo": "pacote"})


# ------------------------------------------------------------------ instalar
def _nome_livre(nome: str, usados: set[str], limite: int) -> str:
    from nicx.rotinas.armazenamento import normalizar

    base, n, atual = nome, 2, nome
    while normalizar(atual) in usados:
        sufixo = f" {n}"
        atual = base[: limite - len(sufixo)] + sufixo
        n += 1
    usados.add(normalizar(atual))
    return atual


def instalar(pacote: dict[str, Any], *, com_mcp: bool = False) -> dict[str, Any]:
    """Instala o que passar na validação; devolve o que entrou e o que ficou de fora.

    Reinstalar o mesmo pacote tira a versão anterior antes (atualização).
    """
    from nicx.assistentes import armazenamento as assistentes
    from nicx.assistentes.modelo import MAX_NOME as MAX_NOME_ASSISTENTE
    from nicx.assistentes.modelo import Assistente
    from nicx.extensoes import habilidades, mcp
    from nicx.rotinas import armazenamento as rotinas
    from nicx.rotinas.armazenamento import normalizar
    from nicx.rotinas.modelo import MAX_NOME as MAX_NOME_ROTINA
    from nicx.rotinas.modelo import Rotina

    with _LOCK:
        if obter_instalado(pacote["id"]) is not None:
            desinstalar(pacote["id"], anotar=False)
        itens: dict[str, list[str]] = {k: [] for k in _LISTAS}
        pulados: list[str] = []

        usados = {normalizar(a.nome) for a in assistentes.listar()}
        for dados in pacote["assistentes"]:
            try:
                a = Assistente.de_dict({**dados, "id": "", "modelo": ""})
                a.nome = _nome_livre(a.nome, usados, MAX_NOME_ASSISTENTE)
                itens["assistentes"].append(assistentes.criar(a).id)
            except ValueError as exc:
                pulados.append(f"assistente {dados.get('nome', '?')}: {exc}")

        usados = {normalizar(r.nome) for r in rotinas.listar()}
        for dados in pacote["rotinas"]:
            try:
                r = Rotina.de_dict({k: v for k, v in dados.items() if k != "id"})
                r.nome = _nome_livre(r.nome, usados, MAX_NOME_ROTINA)
                itens["rotinas"].append(rotinas.criar(r).id)
            except ValueError as exc:
                pulados.append(f"rotina {dados.get('nome', '?')}: {exc}")

        for dados in pacote["habilidades"]:
            titulo = str(dados.get("titulo") or dados.get("nome") or "")
            nome = habilidades.slug(str(dados.get("nome") or titulo))
            if habilidades.obter(nome) is not None:
                pulados.append(f"habilidade {nome}: já existe uma com esse nome")
                continue
            try:
                h = habilidades.salvar(
                    titulo,
                    str(dados.get("descricao", "")),
                    str(dados.get("instrucoes", "")),
                    nome,
                    pacote=pacote["id"],
                )
                itens["habilidades"].append(h.nome)
            except ValueError as exc:
                pulados.append(f"habilidade {nome}: {exc}")

        for dados in pacote["mcp"] if com_mcp else []:
            try:
                s = mcp.Servidor.de_dict({**dados, "id": "", "pacote": pacote["id"]})
                # segredo em branco: entra desligado até o usuário preencher
                falta_token = s.tipo == "http" and "token" in dados and not s.token
                s.ativo = all(s.env.values()) and not falta_token
                s.nome = _nome_livre(s.nome, {x.nome.lower() for x in mcp.listar()}, 40)
                itens["mcp"].append(mcp.criar(s).id)
            except ValueError as exc:
                pulados.append(f"servidor {dados.get('nome', '?')}: {exc}")
        if pacote["mcp"] and not com_mcp:
            pulados.extend(
                f"servidor {s.get('nome', '?')}: não marcado" for s in pacote["mcp"]
            )

        registro = {
            "id": pacote["id"],
            "nome": pacote["nome"],
            "versao": pacote.get("versao", ""),
            "autor": pacote.get("autor", ""),
            "pronto": bool(pacote.get("pronto")),
            "instalado_em": datetime.now().isoformat(timespec="seconds"),
            "itens": itens,
        }
        _gravar([p for p in instalados() if p.get("id") != pacote["id"]] + [registro])
    _anotar(f"Pacote instalado: {pacote['nome']}")
    return {"instalado": registro, "pulados": pulados}


def desinstalar(pacote_id: str, *, anotar: bool = True) -> bool:
    """Tira tudo que o pacote pôs (o que o usuário já apagou é ignorado)."""
    from nicx.assistentes import armazenamento as assistentes
    from nicx.extensoes import habilidades, mcp
    from nicx.rotinas import armazenamento as rotinas

    with _LOCK:
        registro = obter_instalado(pacote_id)
        if registro is None:
            return False
        itens = registro.get("itens") or {}
        for i in itens.get("assistentes", []):
            assistentes.apagar(i)
        for i in itens.get("rotinas", []):
            rotinas.apagar(i)
        for nome in itens.get("habilidades", []):
            try:
                habilidades.apagar(nome)
            except ValueError:
                logger.info("Habilidade %s fora da pasta: mantida", nome)
        for i in itens.get("mcp", []):
            mcp.apagar(i)
        _gravar([p for p in instalados() if p.get("id") != pacote_id])
    if anotar:
        _anotar(f"Pacote removido: {registro.get('nome', pacote_id)}")
    return True


# ------------------------------------------------------------------ exportar
def exportar(
    pacote_id: str,
    nome: str,
    descricao: str = "",
    autor: str = "",
    versao: str = "1.0.0",
    *,
    assistentes_ids: Optional[list[str]] = None,
    rotinas_ids: Optional[list[str]] = None,
    habilidades_nomes: Optional[list[str]] = None,
    mcp_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Monta um pacote com os itens escolhidos (sem segredos)."""
    from nicx.assistentes import armazenamento as assistentes
    from nicx.extensoes import habilidades, mcp
    from nicx.rotinas import armazenamento as rotinas

    if not _ID.match(pacote_id):
        raise PacoteInvalido("id do pacote: letras minúsculas, números e hífen")
    if not nome.strip():
        raise PacoteInvalido("o pacote precisa de um nome")

    def tirar(dados: dict[str, Any], *chaves: str) -> dict[str, Any]:
        return {k: v for k, v in dados.items() if k not in chaves}

    lista_assistentes = [
        tirar(a.para_dict(), "id", "criado_em", "atualizado_em", "modelo")
        for a in assistentes.listar()
        if a.id in set(assistentes_ids or [])
    ]
    lista_rotinas = [
        tirar(r.para_dict(), "id", "criada_em", "ultima_execucao", "ultimo_agendado")
        for r in rotinas.listar()
        if r.id in set(rotinas_ids or [])
    ]
    lista_habilidades = [
        {
            "nome": h.nome,
            "titulo": h.titulo,
            "descricao": h.descricao,
            "instrucoes": h.instrucoes,
        }
        for h in habilidades.listar()
        if h.nome in set(habilidades_nomes or [])
    ]
    lista_mcp = []
    for s in mcp.listar():
        if s.id in set(mcp_ids or []):
            dados = tirar(s.para_dict(), "id", "criado_em", "pacote", "ativo")
            dados["env"] = {k: "" for k in s.env}
            dados["token"] = ""
            lista_mcp.append(dados)
    pacote = {
        "formato": FORMATO,
        "id": pacote_id,
        "nome": " ".join(nome.split())[:60],
        "descricao": " ".join(descricao.split())[:300],
        "versao": versao[:20],
        "autor": " ".join(autor.split())[:60],
        "assistentes": lista_assistentes,
        "rotinas": lista_rotinas,
        "habilidades": lista_habilidades,
        "mcp": lista_mcp,
    }
    if not any(pacote[k] for k in _LISTAS):
        raise PacoteInvalido("escolha pelo menos um item para o pacote")
    return pacote


__all__ = [
    "FORMATO",
    "PacoteInvalido",
    "desinstalar",
    "exportar",
    "instalados",
    "instalar",
    "ler",
    "obter_instalado",
    "permissoes",
    "previa",
]
