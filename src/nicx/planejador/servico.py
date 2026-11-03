"""Planejador de objetivos: etapas com estimativa, datas, lembretes e reajuste.

Um plano é um projeto (``nicx.projetos``) com ``prazo`` e pendências com
``prazo``, ``minutos`` e ``depende_de``. O modelo local só propõe as etapas;
datas, lembretes e progresso são calculados aqui, sem modelo.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_ETAPAS = 12
HORA_LEMBRETE = time(9, 0)
_PENSAMENTO = re.compile(r"<think>.*?</think>", re.S)


@dataclass
class Etapa:
    texto: str
    minutos: int = 60
    depende_de: list[int] = field(default_factory=list)  # índices de etapas anteriores

    def para_dict(self) -> dict[str, Any]:
        return {
            "texto": self.texto,
            "minutos": self.minutos,
            "depende_de": self.depende_de,
        }

    @classmethod
    def de_dict(cls, dados: dict[str, Any], indice: int) -> Optional["Etapa"]:
        texto = " ".join(
            str(
                dados.get("texto") or dados.get("etapa") or dados.get("step") or ""
            ).split()
        )[:300]
        if not texto:
            return None
        try:
            minutos = int(float(dados.get("minutos") or dados.get("minutes") or 60))
        except (TypeError, ValueError):
            minutos = 60
        deps = []
        for d in dados.get("depende_de") or dados.get("depends_on") or []:
            try:
                d = int(d)
            except (TypeError, ValueError):
                continue
            if 0 <= d < indice and d not in deps:
                deps.append(d)
        return cls(texto=texto, minutos=max(15, min(minutos, 6000)), depende_de=deps)


class PlanoErro(ValueError):
    """Pedido de plano que não dá para atender (prazo passado, sem etapas...)."""


# ------------------------------------------------------------- proposta (modelo local)
def _pedido_modelo(objetivo: str, prazo: date, hoje: date, idioma: str) -> str:
    from nicx.nucleo.idiomas import instrucao_resposta

    dias = (prazo - hoje).days
    return (
        "Divida o objetivo abaixo em 3 a 10 etapas práticas, em ordem, para caber "
        f"em {dias} dias (até {prazo.isoformat()}). Para cada etapa, estime o tempo "
        "total de trabalho em minutos e diga de quais etapas anteriores ela depende "
        "(pelo índice, começando em 0). Responda SÓ com um array JSON, sem texto "
        "antes ou depois, no formato "
        '[{"texto": "...", "minutos": 120, "depende_de": []}].'
        + instrucao_resposta(idioma)
        + f"\n\nObjetivo: {objetivo}"
    )


def ler_etapas(resposta: str) -> list[Etapa]:
    """Tira o array JSON da resposta do modelo (tolera texto em volta)."""
    texto = _PENSAMENTO.sub("", resposta or "")
    inicio, fim = texto.find("["), texto.rfind("]")
    if inicio < 0 or fim <= inicio:
        raise PlanoErro("o modelo não devolveu etapas")
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except ValueError as exc:
        raise PlanoErro("o modelo devolveu etapas ilegíveis") from exc
    etapas = []
    for item in dados if isinstance(dados, list) else []:
        if isinstance(item, dict):
            etapa = Etapa.de_dict(item, len(etapas))
            if etapa is not None:
                etapas.append(etapa)
        elif isinstance(item, str) and item.strip():
            etapas.append(Etapa(texto=item.strip()[:300]))
    if not etapas:
        raise PlanoErro("o modelo não devolveu etapas")
    return etapas[:MAX_ETAPAS]


def propor(
    objetivo: str,
    prazo: date,
    idioma: str,
    engine: Any,
    model: str,
    hoje: Optional[date] = None,
) -> list[Etapa]:
    """Pede as etapas ao modelo local. Levanta ``PlanoErro`` se não der."""
    from nicx.nucleo.types import Message, Role

    hoje = hoje or date.today()
    if prazo <= hoje:
        raise PlanoErro("o prazo precisa ser depois de hoje")
    resultado = engine.generate(
        [
            Message(
                role=Role.USER, content=_pedido_modelo(objetivo, prazo, hoje, idioma)
            )
        ],
        model=model,
        temperature=0.2,
        max_tokens=900,
    )
    return ler_etapas(str(resultado.get("content") or ""))


# ------------------------------------------------------------------ datas
def distribuir(minutos: list[int], inicio: date, prazo: date) -> list[date]:
    """Data de cada etapa, proporcional ao tempo, de ``inicio`` até ``prazo``."""
    if not minutos:
        return []
    dias = max(1, (prazo - inicio).days)
    total = sum(max(1, m) for m in minutos)
    datas, acumulado = [], 0
    for m in minutos:
        acumulado += max(1, m)
        datas.append(
            inicio + timedelta(days=max(1, math.ceil(dias * acumulado / total)))
        )
    return [min(d, prazo) for d in datas]


def _lembrete(texto: str, quando: date, nome: str) -> str:
    from nicx.acoes import lembretes
    from nicx.planejador import textos

    momento = datetime.combine(quando, HORA_LEMBRETE)
    if momento <= datetime.now():
        return ""
    return lembretes.add(textos.texto("lembrete", plano=nome, etapa=texto), momento).id


def _anotar_lembretes(
    mudancas_capturadas: list[dict[str, Any]], nome: str, n: int
) -> None:
    """Os lembretes do plano viram uma linha só no histórico (com desfazer de todos)."""
    if not mudancas_capturadas:
        return
    from nicx.historico.registro import anotar
    from nicx.planejador import textos

    principal = dict(mudancas_capturadas[0])
    principal["junto"] = list(principal.get("junto", [])) + mudancas_capturadas[1:]
    anotar(
        "lembrete",
        textos.texto("lembretes_plano", plano=nome, n=n),
        desfazer={"tipo": "colecao", **principal},
    )


# ------------------------------------------------------- criar, progresso, reajustar
def criar_plano(
    objetivo: str,
    prazo: date,
    etapas: list[Etapa],
    *,
    nome: str = "",
    idioma: str = "",
    hoje: Optional[date] = None,
):
    """Cria o projeto do plano com etapas datadas e lembretes; devolve o ``Projeto``."""
    from nicx.historico import mudancas
    from nicx.projetos.armazenamento import Projetos
    from nicx.projetos.modelo import Pendencia

    hoje = hoje or date.today()
    if prazo <= hoje:
        raise PlanoErro("o prazo precisa ser depois de hoje")
    etapas = [e for e in etapas if e.texto][:MAX_ETAPAS]
    if not etapas:
        raise PlanoErro("o plano precisa de pelo menos uma etapa")
    projetos = Projetos()
    nome = (nome or objetivo).strip()[:60]
    projeto = projetos.criar(nome, objetivo=objetivo, idioma=idioma)
    datas = distribuir([e.minutos for e in etapas], hoje, prazo)
    pendencias = [
        Pendencia(texto=e.texto, origem="plano", prazo=d.isoformat(), minutos=e.minutos)
        for e, d in zip(etapas, datas)
    ]
    for etapa, pend in zip(etapas, pendencias):
        pend.depende_de = [
            pendencias[i].id for i in etapa.depende_de if i < len(pendencias)
        ]
    with mudancas.capturar() as capturadas:
        for pend in pendencias:
            pend.lembrete_id = _lembrete(
                pend.texto, date.fromisoformat(pend.prazo), nome
            )
    _anotar_lembretes(capturadas, nome, sum(1 for p in pendencias if p.lembrete_id))

    def aplicar(p):
        p.prazo = prazo.isoformat()
        p.pendencias.extend(pendencias)
        return p

    return projetos._mudar_um(projeto.id, aplicar)


def progresso(projeto, hoje: Optional[date] = None) -> dict[str, Any]:
    hoje = hoje or date.today()
    etapas = [p for p in projeto.pendencias if p.origem == "plano" or p.prazo]
    feitas = [p for p in etapas if p.feita]
    abertas = [p for p in etapas if not p.feita]
    total_min = sum(p.minutos for p in etapas) or 0
    feitos_min = sum(p.minutos for p in feitas)
    atrasadas = [p for p in abertas if p.prazo and p.prazo < hoje.isoformat()]
    proxima = min(abertas, key=lambda p: p.prazo or "9999") if abertas else None
    prazo = date.fromisoformat(projeto.prazo) if projeto.prazo else None
    esperado = 0.0
    if prazo and etapas:
        devidas = [p for p in etapas if p.prazo and p.prazo <= hoje.isoformat()]
        esperado = sum(p.minutos for p in devidas) / (total_min or 1)
    feito = (
        feitos_min / total_min
        if total_min
        else (len(feitas) / len(etapas) if etapas else 0.0)
    )
    return {
        "projeto": projeto.id,
        "nome": projeto.nome,
        "prazo": projeto.prazo,
        "dias_restantes": (prazo - hoje).days if prazo else None,
        "total": len(etapas),
        "feitas": len(feitas),
        "percentual": round(100 * feito),
        "minutos_total": total_min,
        "minutos_feitos": feitos_min,
        "atrasadas": [
            {"id": p.id, "texto": p.texto, "prazo": p.prazo} for p in atrasadas
        ],
        "proxima": {"id": proxima.id, "texto": proxima.texto, "prazo": proxima.prazo}
        if proxima
        else None,
        "no_ritmo": feito + 1e-9 >= esperado,
    }


def reajustar(
    projeto_id: str, novo_prazo: Optional[date] = None, hoje: Optional[date] = None
):
    """Redistribui as etapas abertas de amanhã até o prazo (ou o novo prazo)."""
    from nicx.acoes import lembretes
    from nicx.historico import mudancas
    from nicx.projetos.armazenamento import Projetos

    hoje = hoje or date.today()
    projetos = Projetos()
    projeto = projetos.obter(projeto_id)
    if projeto is None:
        raise PlanoErro("plano não encontrado")
    prazo = novo_prazo or (date.fromisoformat(projeto.prazo) if projeto.prazo else None)
    if prazo is None or prazo <= hoje:
        raise PlanoErro("o prazo já passou: escolha um novo")
    abertas = [p for p in projeto.abertas if p.origem == "plano" or p.prazo]
    datas = distribuir([p.minutos or 60 for p in abertas], hoje, prazo)
    novos: dict[str, tuple[str, str]] = {}
    with mudancas.capturar() as capturadas:
        for pend, quando in zip(abertas, datas):
            if pend.lembrete_id:
                lembretes.cancel_id(pend.lembrete_id)
            novos[pend.id] = (
                quando.isoformat(),
                _lembrete(pend.texto, quando, projeto.nome),
            )
    _anotar_lembretes(capturadas, projeto.nome, len(novos))

    def aplicar(p):
        p.prazo = prazo.isoformat()
        for pend in p.pendencias:
            if pend.id in novos:
                pend.prazo, pend.lembrete_id = novos[pend.id]
        return p

    return projetos._mudar_um(projeto_id, aplicar)


def frase_do_plano(projeto, idioma: Optional[str] = None) -> str:
    from nicx.planejador import textos

    info = progresso(projeto)
    proxima = info["proxima"]
    texto = textos.texto(
        "criado",
        idioma,
        plano=projeto.nome,
        n=info["total"],
        prazo=_data(projeto.prazo, idioma),
    )
    if proxima:
        texto += textos.texto(
            "primeira",
            idioma,
            etapa=proxima["texto"],
            prazo=_data(proxima["prazo"], idioma),
        )
    return texto


def _data(iso: str, idioma: Optional[str]) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return (
        d.strftime("%m/%d") if (idioma or "").startswith("en") else d.strftime("%d/%m")
    )


__all__ = [
    "Etapa",
    "PlanoErro",
    "criar_plano",
    "distribuir",
    "frase_do_plano",
    "ler_etapas",
    "progresso",
    "propor",
    "reajustar",
]
