"""O ``Projeto`` e suas partes (decisões e pendências).

Datas em ISO, hora local sem fuso (``2026-10-30T14:05:00``), como nos
lembretes e na agenda: o "dia" de uma atividade é o dia do relógio do PC.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Optional

# Limites: o arquivo fica pequeno e o resumo cabe no prompt.
MAX_NOME = 80
MAX_TEXTO = 500
MAX_DECISOES = 200
MAX_PENDENCIAS = 300
MAX_PASSOS = 20
MAX_CAMINHOS = 30
MAX_DIAS_ATIVOS = 120


def agora() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def novo_id() -> str:
    return uuid.uuid4().hex[:10]


def dia_de(iso: str) -> Optional[date]:
    """O dia de uma data ISO; None se estiver vazia ou inválida."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).date()
    except ValueError:
        return None


def limpar_texto(texto: Any, limite: int = MAX_TEXTO) -> str:
    """Uma linha só, sem espaços sobrando, cortada no limite."""
    texto = " ".join(str(texto or "").split())
    return texto[:limite].rstrip()


@dataclass
class Decisao:
    texto: str
    data: str = field(default_factory=agora)
    # "" = o usuário pediu; "auto" = sugerida pela memória automática.
    origem: str = ""


@dataclass
class Pendencia:
    texto: str
    id: str = field(default_factory=novo_id)
    feita: bool = False
    criada_em: str = field(default_factory=agora)
    feita_em: str = ""
    origem: str = ""


@dataclass
class Projeto:
    nome: str
    id: str = field(default_factory=novo_id)
    objetivo: str = ""
    # Resumo curto do ponto atual ("API pronta, falta a tela de login").
    estado: str = ""
    pastas: list[str] = field(default_factory=list)
    arquivos: list[str] = field(default_factory=list)
    decisoes: list[Decisao] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    proximos_passos: list[str] = field(default_factory=list)
    criado_em: str = field(default_factory=agora)
    ultima_atividade: str = field(default_factory=agora)
    idioma: str = ""
    arquivado: bool = False
    # Dias (ISO) em que houve atividade: o resumo do dia olha aqui.
    dias_ativos: list[str] = field(default_factory=list)

    @property
    def abertas(self) -> list[Pendencia]:
        return [p for p in self.pendencias if not p.feita]

    def marcar_atividade(self, quando: Optional[str] = None) -> None:
        quando = quando or agora()
        if quando > self.ultima_atividade:
            self.ultima_atividade = quando
        dia = quando[:10]
        if dia not in self.dias_ativos:
            self.dias_ativos.append(dia)
            self.dias_ativos.sort()
            del self.dias_ativos[:-MAX_DIAS_ATIVOS]

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Projeto":
        """Lê um projeto do JSON; levanta ``ValueError`` se não der."""
        if not isinstance(dados, dict):
            raise ValueError("projeto não é um objeto")
        nome = limpar_texto(dados.get("nome"), MAX_NOME)
        pid = str(dados.get("id") or "").strip()
        if not nome or not pid:
            raise ValueError("projeto sem nome ou id")

        def textos(chave: str, limite: int) -> list[str]:
            valor = dados.get(chave) or []
            if not isinstance(valor, list):
                return []
            return [t for t in (limpar_texto(v, 1000) for v in valor) if t][:limite]

        decisoes = []
        for item in dados.get("decisoes") or []:
            if isinstance(item, dict) and limpar_texto(item.get("texto")):
                decisoes.append(
                    Decisao(
                        texto=limpar_texto(item.get("texto")),
                        data=str(item.get("data") or ""),
                        origem=str(item.get("origem") or ""),
                    )
                )
        pendencias = []
        for item in dados.get("pendencias") or []:
            if isinstance(item, dict) and limpar_texto(item.get("texto")):
                pendencias.append(
                    Pendencia(
                        texto=limpar_texto(item.get("texto")),
                        id=str(item.get("id") or novo_id()),
                        feita=bool(item.get("feita", False)),
                        criada_em=str(item.get("criada_em") or ""),
                        feita_em=str(item.get("feita_em") or ""),
                        origem=str(item.get("origem") or ""),
                    )
                )
        criado = str(dados.get("criado_em") or "")
        return cls(
            nome=nome,
            id=pid,
            objetivo=limpar_texto(dados.get("objetivo"), 1000),
            estado=limpar_texto(dados.get("estado"), 1000),
            pastas=textos("pastas", MAX_CAMINHOS),
            arquivos=textos("arquivos", MAX_CAMINHOS),
            decisoes=decisoes[-MAX_DECISOES:],
            pendencias=pendencias[-MAX_PENDENCIAS:],
            proximos_passos=textos("proximos_passos", MAX_PASSOS),
            criado_em=criado,
            ultima_atividade=str(dados.get("ultima_atividade") or criado),
            idioma=str(dados.get("idioma") or ""),
            arquivado=bool(dados.get("arquivado", False)),
            dias_ativos=[
                d
                for d in (dados.get("dias_ativos") or [])
                if isinstance(d, str) and dia_de(d)
            ][-MAX_DIAS_ATIVOS:],
        )


__all__ = [
    "MAX_NOME",
    "MAX_TEXTO",
    "Decisao",
    "Pendencia",
    "Projeto",
    "agora",
    "dia_de",
    "limpar_texto",
    "novo_id",
]
