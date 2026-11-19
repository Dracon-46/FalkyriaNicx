"""A tarefa do modo Trabalho e onde ela fica guardada.

``~/.nicx/trabalho/<id>/tarefa.json`` (estado, plano, registro, diário de
mudanças), ``copias/`` (o que era antes de cada arquivo mudado) e
``lixeira/`` (o que foi apagado). Tudo isso serve para desfazer a tarefa.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Estados
PLANEJANDO = "planejando"
AGUARDANDO_APROVACAO = "aguardando_aprovacao"
EXECUTANDO = "executando"
PAUSADA = "pausada"
AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao"
CONCLUIDA = "concluida"
PARADA = "parada"
ERRO = "erro"
DESFEITA = "desfeita"
INTERROMPIDA = "interrompida"  # o Nicx fechou no meio

ATIVOS = {PLANEJANDO, EXECUTANDO, PAUSADA, AGUARDANDO_CONFIRMACAO}
MAX_REGISTRO = 400
_LOCK = threading.RLock()


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Passo:
    descricao: str
    estado: str = "pendente"  # pendente | fazendo | feito | falhou | pulado
    resultado: str = ""


@dataclass
class Tarefa:
    id: str
    pasta: str
    pedido: str
    estado: str = PLANEJANDO
    plano: list[Passo] = field(default_factory=list)
    registro: list[dict[str, Any]] = field(default_factory=list)
    diario: list[dict[str, Any]] = field(default_factory=list)
    pergunta: Optional[dict[str, Any]] = None
    resumo: str = ""
    erro: str = ""
    criado_em: str = field(default_factory=agora)
    atualizado_em: str = field(default_factory=agora)
    ferramentas_usadas: int = 0

    # ------------------------------------------------------------ registro
    def anotar(self, tipo: str, texto: str) -> None:
        with _LOCK:
            self.registro.append(
                {"quando": agora(), "tipo": tipo, "texto": texto[:2000]}
            )
            if len(self.registro) > MAX_REGISTRO:
                self.registro = self.registro[-MAX_REGISTRO:]

    def arquivos_mudados(self) -> list[str]:
        vistos: list[str] = []
        for d in self.diario:
            for chave in ("caminho", "para"):
                c = d.get(chave)
                if c and c not in vistos:
                    vistos.append(c)
        return vistos

    # --------------------------------------------------------- persistência
    def para_dict(self) -> dict[str, Any]:
        with _LOCK:
            d = asdict(self)
        d["arquivos_mudados"] = self.arquivos_mudados()
        return d

    @classmethod
    def de_dict(cls, d: dict[str, Any]) -> "Tarefa":
        plano = [Passo(**p) for p in d.get("plano", [])]
        campos = {
            k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "plano"
        }
        return cls(plano=plano, **campos)


def pasta_dados() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "trabalho"


def pasta_da_tarefa(tarefa_id: str) -> Path:
    if not tarefa_id.isalnum():
        raise ValueError("id de tarefa inválido")
    return pasta_dados() / tarefa_id


def novo_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)


def salvar(tarefa: Tarefa) -> None:
    with _LOCK:
        tarefa.atualizado_em = agora()
        destino = pasta_da_tarefa(tarefa.id)
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / "tarefa.json"
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(
            json.dumps(tarefa.para_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        temporario.replace(arquivo)


def carregar(tarefa_id: str) -> Optional[Tarefa]:
    try:
        arquivo = pasta_da_tarefa(tarefa_id) / "tarefa.json"
        return Tarefa.de_dict(json.loads(arquivo.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def listar() -> list[Tarefa]:
    base = pasta_dados()
    if not base.is_dir():
        return []
    tarefas = [t for p in base.iterdir() if p.is_dir() and (t := carregar(p.name))]
    return sorted(tarefas, key=lambda t: t.criado_em, reverse=True)


__all__ = [
    "AGUARDANDO_APROVACAO",
    "AGUARDANDO_CONFIRMACAO",
    "ATIVOS",
    "CONCLUIDA",
    "DESFEITA",
    "ERRO",
    "EXECUTANDO",
    "INTERROMPIDA",
    "PARADA",
    "PAUSADA",
    "PLANEJANDO",
    "Passo",
    "Tarefa",
    "carregar",
    "listar",
    "novo_id",
    "pasta_da_tarefa",
    "salvar",
]
