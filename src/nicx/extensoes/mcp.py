"""Servidores MCP que o usuário adiciona (tela, ``nicx add`` ou pacote).

Ficam em ``~/.nicx/mcp.json``. Um servidor é um programa local (stdio:
``npx -y @modelcontextprotocol/server-filesystem C:/pasta``) ou um endereço
HTTP. As ferramentas dele entram no agente do chat sem reiniciar o Nicx
(:func:`recarregar`).

Segurança:

- só o usuário adiciona servidores (o modelo não tem ferramenta para isso);
- token e variáveis de ambiente nunca voltam inteiros pela API (:func:`publico`);
- as ferramentas de um servidor têm o risco da ``confianca`` dele no nível de
  autonomia: ``perguntar`` (padrão, moderado), ``livre`` (leitura) ou
  ``sempre`` (alto: pede "confirmo" em todo nível).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MASCARA = "••••••"
CONFIANCAS = {"perguntar": "moderado", "livre": "leitura", "sempre": "alto"}
TIPOS = ("stdio", "http")
PRAZO_TESTE_S = 90.0  # npx baixa o pacote na primeira vez
_LOCK = threading.RLock()
_NOME = re.compile(r"^[\w .-]{1,40}$", re.UNICODE)


class ServidorInvalido(ValueError):
    """Campo fora do esperado; a mensagem diz qual."""


@dataclass
class Servidor:
    nome: str
    tipo: str = "stdio"
    comando: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    token: str = ""
    incluir: list[str] = field(default_factory=list)
    excluir: list[str] = field(default_factory=list)
    ativo: bool = True
    confianca: str = "perguntar"
    descricao: str = ""
    pacote: str = ""  # id do pacote que o instalou, se veio de um
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    criado_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Servidor":
        def lista(chave: str) -> list[str]:
            valor = dados.get(chave) or []
            return [str(v) for v in valor] if isinstance(valor, list) else []

        env = dados.get("env") or {}
        base = cls(nome="")
        return cls(
            nome=" ".join(str(dados.get("nome", "") or "").split()),
            tipo=str(dados.get("tipo") or ("http" if dados.get("url") else "stdio")),
            comando=str(dados.get("comando", "") or "").strip(),
            args=lista("args"),
            env={str(k): str(v) for k, v in env.items()}
            if isinstance(env, dict)
            else {},
            url=str(dados.get("url", "") or "").strip(),
            token=str(dados.get("token", "") or ""),
            incluir=lista("incluir"),
            excluir=lista("excluir"),
            ativo=bool(dados.get("ativo", True)),
            confianca=str(dados.get("confianca") or "perguntar"),
            descricao=" ".join(str(dados.get("descricao", "") or "").split())[:200],
            pacote=str(dados.get("pacote", "") or ""),
            id=str(dados.get("id") or base.id),
            criado_em=str(dados.get("criado_em") or base.criado_em),
        )

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    def para_loader(self) -> dict[str, Any]:
        """No formato de ``load_mcp_tools_from_config`` (chaves em inglês)."""
        return {
            "name": self.nome,
            "url": self.url if self.tipo == "http" else "",
            "token": self.token or None,
            "command": self.comando if self.tipo == "stdio" else "",
            "args": list(self.args),
            "env": dict(self.env),
            "include_tools": list(self.incluir),
            "exclude_tools": list(self.excluir),
        }


def validar(s: Servidor) -> None:
    if not _NOME.match(s.nome or ""):
        raise ServidorInvalido("nome: até 40 letras, números, espaço, ponto ou hífen")
    if s.tipo not in TIPOS:
        raise ServidorInvalido("tipo: stdio ou http")
    if s.confianca not in CONFIANCAS:
        raise ServidorInvalido("confiança: perguntar, livre ou sempre")
    if s.tipo == "stdio" and not s.comando:
        raise ServidorInvalido("falta o comando")
    if s.tipo == "http" and not re.match(r"^https?://", s.url):
        raise ServidorInvalido("o endereço precisa começar com http:// ou https://")
    if len(s.args) > 40 or len(s.env) > 40:
        raise ServidorInvalido("argumentos ou variáveis demais")


def publico(s: Servidor) -> dict[str, Any]:
    """Para a API: token e valores do ambiente escondidos."""
    dados = s.para_dict()
    dados["token"] = MASCARA if s.token else ""
    dados["env"] = {k: (MASCARA if v else "") for k, v in s.env.items()}
    return dados


def com_segredos_antigos(novo: Servidor, antigo: Optional[Servidor]) -> Servidor:
    """A tela devolve a máscara no lugar do que não mudou: mantém o valor guardado."""
    if antigo is None:
        return novo
    if novo.token == MASCARA:
        novo.token = antigo.token
    novo.env = {
        k: (antigo.env.get(k, "") if v == MASCARA else v) for k, v in novo.env.items()
    }
    return novo


# ------------------------------------------------------------------ arquivo
def caminho() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "mcp.json"


def _ler() -> list[dict[str, Any]]:
    arquivo = caminho()
    if not arquivo.exists():
        return []
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("mcp.json ilegível; guardando cópia e começando vazio")
        try:
            arquivo.replace(arquivo.with_suffix(".json.corrompido"))
        except OSError:
            pass
        return []
    return [d for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []


def _gravar(servidores: list[Servidor]) -> None:
    arquivo = caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    texto = json.dumps(
        [s.para_dict() for s in servidores], ensure_ascii=False, indent=1
    )
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, arquivo)


def _anotar(chave: str, nome: str) -> None:
    from nicx.historico.registro import anotar

    titulos = {
        "criado": "Servidor MCP adicionado: {}",
        "alterado": "Servidor MCP alterado: {}",
        "apagado": "Servidor MCP removido: {}",
    }
    anotar("extensao", titulos[chave].format(nome), detalhe={"tipo": "mcp"})


def listar() -> list[Servidor]:
    with _LOCK:
        return [Servidor.de_dict(d) for d in _ler()]


def obter(servidor_id: str) -> Optional[Servidor]:
    return next((s for s in listar() if s.id == servidor_id), None)


def _nome_livre(nome: str, servidores: list[Servidor], exceto: str = "") -> None:
    if nome.lower() in {s.nome.lower() for s in servidores if s.id != exceto}:
        raise ServidorInvalido(f"já existe um servidor chamado {nome}")


def criar(servidor: Servidor) -> Servidor:
    validar(servidor)
    with _LOCK:
        servidores = listar()
        _nome_livre(servidor.nome, servidores)
        servidores.append(servidor)
        _gravar(servidores)
    _anotar("criado", servidor.nome)
    return servidor


def atualizar(servidor_id: str, novo: Servidor) -> Servidor:
    with _LOCK:
        servidores = listar()
        for i, s in enumerate(servidores):
            if s.id == servidor_id:
                novo = com_segredos_antigos(novo, s)
                novo.id, novo.criado_em, novo.pacote = s.id, s.criado_em, s.pacote
                validar(novo)
                _nome_livre(novo.nome, servidores, exceto=s.id)
                servidores[i] = novo
                _gravar(servidores)
                break
        else:
            raise KeyError(servidor_id)
    _anotar("alterado", novo.nome)
    return novo


def apagar(servidor_id: str) -> bool:
    with _LOCK:
        servidores = listar()
        restantes = [s for s in servidores if s.id != servidor_id]
        if len(restantes) == len(servidores):
            return False
        _gravar(restantes)
    nome = next(s.nome for s in servidores if s.id == servidor_id)
    _anotar("apagado", nome)
    return True


# ------------------------------------------------------------- ferramentas
# nome da ferramenta -> (servidor, risco); preenchido ao carregar
_FERRAMENTAS: dict[str, tuple[str, str]] = {}
# id do servidor -> situação da última carga (para a tela)
_SITUACAO: dict[str, dict[str, Any]] = {}
# o que está ligado agora (para trocar na recarga)
_POOL: dict[str, list[Any]] = {"tools": [], "clients": []}


def risco_de(ferramenta: str) -> Optional[str]:
    """Risco de uma ferramenta MCP no nível de autonomia (None = não é MCP)."""
    achado = _FERRAMENTAS.get(ferramenta)
    return achado[1] if achado else None


def servidor_da_ferramenta(ferramenta: str) -> Optional[str]:
    achado = _FERRAMENTAS.get(ferramenta)
    return achado[0] if achado else None


def situacao() -> dict[str, dict[str, Any]]:
    return {k: dict(v) for k, v in _SITUACAO.items()}


def _carregar_um(servidor: Servidor) -> tuple[list[Any], list[Any]]:
    from types import SimpleNamespace

    from nicx.ferramentas.mcp.loader import load_mcp_tools_from_config

    cfg = SimpleNamespace(enabled=True, servers=[servidor.para_loader()])
    return load_mcp_tools_from_config(cfg)


def carregar() -> tuple[list[Any], list[Any]]:
    """Liga os servidores ativos; devolve ``(ferramentas, clientes)``.

    Um servidor que falha fica de fora (a situação dele guarda o erro). Nomes
    repetidos entre servidores: o primeiro ganha.
    """
    tools: list[Any] = []
    clients: list[Any] = []
    vistos: set[str] = set()
    _FERRAMENTAS.clear()
    _SITUACAO.clear()
    for servidor in listar():
        if not servidor.ativo:
            _SITUACAO[servidor.id] = {"estado": "desligado", "ferramentas": []}
            continue
        try:
            achadas, clientes = _carregar_um(servidor)
        except Exception as exc:  # noqa: BLE001 - cada servidor por si
            achadas, clientes = [], []
            logger.warning("Servidor MCP %s não ligou: %s", servidor.nome, exc)
        clients.extend(clientes)
        novas = [t for t in achadas if t.spec.name not in vistos]
        for t in novas:
            vistos.add(t.spec.name)
            t._nicx_extensao = servidor.id
            _FERRAMENTAS[t.spec.name] = (servidor.nome, CONFIANCAS[servidor.confianca])
        tools.extend(novas)
        _SITUACAO[servidor.id] = {
            "estado": "ligado" if clientes else "erro",
            "ferramentas": [t.spec.name for t in novas],
            "erro": "" if clientes else "não respondeu (veja o comando e os logs)",
        }
    _POOL["tools"], _POOL["clients"] = list(tools), list(clients)
    return tools, clients


def testar(servidor: Servidor, prazo: float = PRAZO_TESTE_S) -> dict[str, Any]:
    """Liga, lista as ferramentas e desliga. Não grava nada."""
    resultado: dict[str, Any] = {"ok": False, "ferramentas": [], "erro": ""}

    def rodar() -> None:
        try:
            tools, clients = _carregar_um(servidor)
            resultado["ok"] = bool(clients)
            resultado["ferramentas"] = [
                {"nome": t.spec.name, "descricao": t.spec.description[:200]}
                for t in tools
            ]
            if not clients:
                resultado["erro"] = "o servidor não respondeu"
            for c in clients:
                try:
                    c.close()
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            resultado["erro"] = str(exc)[:300]

    t = threading.Thread(target=rodar, name="nicx-mcp-teste", daemon=True)
    t.start()
    t.join(prazo)
    if t.is_alive():
        resultado["erro"] = f"passou de {int(prazo)} s sem responder"
    return resultado


def recarregar(app_state: Any) -> dict[str, dict[str, Any]]:
    """Troca as ferramentas MCP do agente do chat pelas dos servidores atuais.

    Espera o pedido em andamento terminar (o mesmo cadeado da troca de modelo).
    """
    antigas, antigos_clientes = list(_POOL["tools"]), list(_POOL["clients"])
    tools, clients = carregar()
    agent = getattr(app_state, "agent", None)
    if agent is not None and hasattr(agent, "_tools"):
        from nicx.servidor.rotas.chat import _get_agent_model_lock

        with _get_agent_model_lock(agent):
            ids_antigas = {id(t) for t in antigas}
            atuais = [t for t in agent._tools if id(t) not in ids_antigas]
            existentes = {t.spec.name for t in atuais}
            atuais.extend(t for t in tools if t.spec.name not in existentes)
            agent._tools[:] = atuais
            executor = getattr(agent, "_executor", None)
            if executor is not None and isinstance(
                getattr(executor, "_tools", None), dict
            ):
                executor._tools = {t.spec.name: t for t in atuais}
    lista = getattr(app_state, "mcp_tools", None)
    if isinstance(lista, list):
        ids_antigas = {id(t) for t in antigas}
        lista[:] = [t for t in lista if id(t) not in ids_antigas] + tools
    trava = getattr(app_state, "_mcp_clients_lock", None)
    clientes_app = getattr(app_state, "_mcp_clients", None)
    if trava is not None and isinstance(clientes_app, list):
        with trava:
            ids = {id(c) for c in antigos_clientes}
            clientes_app[:] = [c for c in clientes_app if id(c) not in ids] + clients
    for c in antigos_clientes:
        try:
            c.close()
        except Exception:  # noqa: BLE001
            logger.debug("MCP: cliente antigo não fechou", exc_info=True)
    return situacao()


__all__ = [
    "CONFIANCAS",
    "MASCARA",
    "Servidor",
    "ServidorInvalido",
    "apagar",
    "atualizar",
    "carregar",
    "criar",
    "listar",
    "obter",
    "publico",
    "recarregar",
    "risco_de",
    "situacao",
    "testar",
]
