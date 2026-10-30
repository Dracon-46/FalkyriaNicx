"""Junta o que aconteceu num dia e escreve o resumo, sem modelo.

Fontes (todas no PC, só leitura):

- lembretes que tocaram (``~/.nicx/lembretes_disparados.json``) e os que
  ainda vêm no dia (``lembretes.json``); timers, alarmes e os avisos da
  agenda ficam de fora (o compromisso já aparece);
- compromissos da agenda (``agenda.json``) e os que os conectores trouxeram
  do Google Agenda/Outlook, divididos em já passaram / ainda vêm, e os do
  dia seguinte;
- anotações (``notas.md``): quantas e as 3 últimas, curtas;
- pastas organizadas (``~/.nicx/organizacao/``);
- projetos (``nicx.projetos.resumo_do_dia``), se o módulo existir.

Nada disso vai para analytics nem para os logs.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from nicx.resumo.textos import codigo, texto

logger = logging.getLogger(__name__)

# Quantos itens cada frase fala antes do "e mais N".
LIMITE_ITENS = 5
ULTIMAS_NOTAS = 3
TAMANHO_NOTA = 50
LIMITE_PENDENTES = 10


@dataclass
class Item:
    """Um compromisso ou lembrete. ``hora`` None: dia todo."""

    titulo: str
    hora: Optional[datetime] = None

    def como_dict(self) -> dict:
        return {
            "titulo": self.titulo,
            "hora": f"{self.hora:%H:%M}" if self.hora is not None else None,
        }


@dataclass
class Resumo:
    dia: date
    idioma: str
    agora: datetime
    lembretes_feitos: List[str] = field(default_factory=list)
    lembretes_restantes: List[Item] = field(default_factory=list)
    compromissos_feitos: List[Item] = field(default_factory=list)
    compromissos_restantes: List[Item] = field(default_factory=list)
    compromissos_seguinte: List[Item] = field(default_factory=list)
    notas_total: int = 0
    notas_ultimas: List[str] = field(default_factory=list)
    organizacoes: List[tuple[str, int]] = field(default_factory=list)
    projetos_atualizados: List[str] = field(default_factory=list)
    pendencias_concluidas: List[tuple[str, str]] = field(default_factory=list)
    pendencias_abertas: List[tuple[str, str]] = field(default_factory=list)
    texto: str = ""
    texto_pendente: str = ""

    def como_dict(self) -> dict:
        return {
            "dia": self.dia.isoformat(),
            "idioma": self.idioma,
            "texto": self.texto,
            "texto_pendente": self.texto_pendente,
            "secoes": {
                "lembretes_feitos": list(self.lembretes_feitos),
                "lembretes_restantes": [
                    i.como_dict() for i in self.lembretes_restantes
                ],
                "compromissos_feitos": [
                    i.como_dict() for i in self.compromissos_feitos
                ],
                "compromissos_restantes": [
                    i.como_dict() for i in self.compromissos_restantes
                ],
                "compromissos_seguinte": [
                    i.como_dict() for i in self.compromissos_seguinte
                ],
                "notas_total": self.notas_total,
                "notas_ultimas": list(self.notas_ultimas),
                "organizacoes": [
                    {"pasta": p, "arquivos": n} for p, n in self.organizacoes
                ],
                "projetos_atualizados": list(self.projetos_atualizados),
                "pendencias_concluidas": [
                    {"projeto": p, "pendencia": t}
                    for p, t in self.pendencias_concluidas
                ],
                "pendencias_abertas": [
                    {"projeto": p, "pendencia": t} for p, t in self.pendencias_abertas
                ],
            },
        }


# ---------------------------------------------------------------------------
# Hora local (fuso da agenda, America/Sao_Paulo por padrão)
# ---------------------------------------------------------------------------


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def agora_local() -> datetime:
    """Agora, sem fuso, no fuso de ``[agenda] fuso`` (ou o do PC)."""
    try:
        from zoneinfo import ZoneInfo

        from nicx.acoes import calendarios

        fuso = ZoneInfo(calendarios.fuso())
    except Exception:  # noqa: BLE001 - sem tzdata: o relógio do PC
        return _agora_utc().astimezone().replace(tzinfo=None)
    return _agora_utc().astimezone(fuso).replace(tzinfo=None)


def hoje() -> date:
    return agora_local().date()


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------


def _config_dir() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir()


def _curta(text: str, limite: int = TAMANHO_NOTA) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limite:
        return text
    return text[: limite - 1].rstrip() + "…"


@dataclass
class _Compromisso:
    titulo: str
    inicio: datetime
    fim: datetime
    dia_todo: bool

    def item(self) -> Item:
        return Item(self.titulo, None if self.dia_todo else self.inicio)


def _compromissos(dia: date) -> List[_Compromisso]:
    """Agenda local + eventos sincronizados, sem repetir o mesmo evento."""
    from nicx.acoes import agenda, calendarios

    try:
        eventos = agenda.on_day(dia)
    except Exception as exc:  # noqa: BLE001
        logger.info("Agenda indisponível no resumo: %s", exc)
        eventos = []
    lista = [_Compromisso(e.title, e.start_at, e.end_at, e.all_day) for e in eventos]
    enviados = {e.google_id for e in eventos if e.google_id}
    enviados |= {e.outlook_id for e in eventos if e.outlook_id}
    locais = {(e.title.casefold(), e.start_at) for e in eventos}
    try:
        remotos = calendarios.eventos_conectados(dia)
    except Exception:  # noqa: BLE001 - a agenda local responde sozinha
        remotos = []
    for r in remotos:
        if (r.remote_id and r.remote_id in enviados) or (
            r.title.casefold(),
            r.start,
        ) in locais:
            continue
        if r.all_day:
            fim = datetime.combine(
                r.start.date() + timedelta(days=1), datetime.min.time()
            )
        else:
            fim = r.start + agenda.DEFAULT_DURATION
        lista.append(_Compromisso(r.title, r.start, fim, r.all_day))
    lista.sort(key=lambda c: (not c.dia_todo, c.inicio))
    return lista


def _avisos_da_agenda(dia: date) -> set[str]:
    """Ids dos lembretes que são o aviso de um compromisso."""
    from nicx.acoes import agenda

    ids: set[str] = set()
    for d in (dia, dia + timedelta(days=1)):
        try:
            ids |= {e.reminder_id for e in agenda.on_day(d) if e.reminder_id}
        except Exception:  # noqa: BLE001
            continue
    return ids


def _lembretes(dia: date) -> tuple[List[str], List[Item]]:
    from nicx.acoes import lembretes

    avisos = _avisos_da_agenda(dia)

    def conta(r: Any) -> bool:
        return lembretes.kind_of(r) == "lembrete" and r.id not in avisos

    feitos = [r.text for r in lembretes.fired_on(dia) if conta(r)]
    restantes = [
        Item(r.text, r.due_at)
        for r in lembretes.pending()
        if r.due_at.date() == dia and conta(r)
    ]
    return feitos, restantes


_NOTA = re.compile(r"^- \[(?P<d>\d{1,2})/(?P<m>\d{1,2})(?: [^\]]*)?\] (?P<t>.+)$")


def _notas(dia: date, agora: datetime) -> List[str]:
    """Anotações do dia, na ordem em que foram feitas.

    As linhas só têm dia e mês ("[27/10 14:05]"). Como o arquivo cresce em
    ordem, o ano sai de trás para frente: cada nota é do dia/mês mais recente
    que não passa da nota seguinte (a última, de hoje).
    """
    from nicx.acoes import notas

    arquivo = notas.path()
    if not arquivo.exists():
        return []
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    achadas: List[str] = []
    limite = agora.date()
    for linha in reversed(linhas):
        m = _NOTA.match(linha.strip())
        if not m:
            continue
        d, mes = int(m.group("d")), int(m.group("m"))
        try:
            quando = date(limite.year, mes, d)
            if quando > limite:
                quando = date(limite.year - 1, mes, d)
        except ValueError:
            continue
        limite = quando
        if quando == dia:
            achadas.append(m.group("t").strip())
        elif quando < dia:
            break
    achadas.reverse()
    return achadas


def _organizacoes(dia: date) -> List[tuple[str, int]]:
    """Pastas organizadas no dia (as desfeitas não contam) e quantos arquivos."""
    pasta = _config_dir() / "organizacao"
    if not pasta.is_dir():
        return []
    totais: dict[str, int] = {}
    for log in sorted(pasta.glob(f"{dia:%Y%m%d}-*.json")):
        try:
            dados = json.loads(log.read_text(encoding="utf-8"))
            caminho = str(dados.get("folder", ""))
            movidos = len(dados.get("moves") or [])
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        if not movidos:
            continue
        nome = re.split(r"[\\/]", caminho.rstrip("\\/"))[-1] or caminho
        totais[nome] = totais.get(nome, 0) + movidos
    return list(totais.items())


def _pares(valor: Any) -> List[tuple[str, str]]:
    pares: List[tuple[str, str]] = []
    for par in valor or []:
        try:
            projeto, tarefa = par
        except (TypeError, ValueError):
            continue
        if str(tarefa).strip():
            pares.append((str(projeto), str(tarefa)))
    return pares


def _projetos(
    dia: date,
) -> tuple[List[str], List[tuple[str, str]], List[tuple[str, str]]]:
    """``nicx.projetos.resumo_do_dia``: atualizados, concluídas, pendentes."""
    try:
        from nicx.projetos import resumo_do_dia
    except ImportError:
        return [], [], []
    try:
        dados = resumo_do_dia(dia)
    except Exception as exc:  # noqa: BLE001 - o resto do resumo continua
        logger.info("Projetos indisponíveis no resumo: %s", exc)
        return [], [], []
    if not isinstance(dados, dict):
        return [], [], []
    atualizados = [str(p) for p in dados.get("atualizados") or [] if str(p).strip()]
    concluidas = _pares(dados.get("concluidas"))
    pendentes = _pares(dados.get("pendentes"))[:LIMITE_PENDENTES]
    return atualizados, concluidas, pendentes


def _seguro(nome: str, funcao, vazio):
    """Uma fonte com problema não derruba o resumo inteiro."""
    try:
        return funcao()
    except Exception as exc:  # noqa: BLE001
        logger.info("Fonte %s indisponível no resumo: %s", nome, exc)
        return vazio


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------


def _lista(itens: List[str], cod: str, limite: int = LIMITE_ITENS) -> str:
    texto_ = texto("sep", cod).join(itens[:limite])
    if len(itens) > limite:
        texto_ += texto("e_mais", cod, n=len(itens) - limite)
    return texto_


def _item(item: Item, cod: str) -> str:
    if item.hora is None:
        return texto("item_dia_todo", cod, titulo=item.titulo)
    from nicx.acoes.textos import hora_curta

    return texto(
        "item_hora",
        cod,
        titulo=item.titulo,
        hora=hora_curta(item.hora, cod),
        a_las="a la" if item.hora.hour == 1 else "a las",
    )


def _datas(dia: date) -> dict[str, object]:
    return {
        "dd": f"{dia.day:02d}",
        "mm": f"{dia.month:02d}",
        "d": dia.day,
        "m": dia.month,
    }


def _relativo(dia: date, agora: datetime) -> str:
    dias = (dia - agora.date()).days
    return {0: "hoje", -1: "ontem"}.get(dias, "data")


def _frase_final(r: Resumo) -> str:
    """'Amanhã você tem…' (ou 'Hoje você tem…' no resumo de ontem)."""
    quando = _relativo(r.dia, r.agora)
    if quando == "data":
        return ""
    prefixo = "amanha" if quando == "hoje" else "hoje"
    if not r.compromissos_seguinte:
        return texto(f"{prefixo}_livre", r.idioma)
    itens = [_item(i, r.idioma) for i in r.compromissos_seguinte]
    return texto(f"{prefixo}_tem", r.idioma, itens=_lista(itens, r.idioma))


def _projeto_itens(pares: List[tuple[str, str]], cod: str) -> List[str]:
    return [texto("proj_item", cod, tarefa=t, projeto=p) for p, t in pares]


def _secoes_pendentes(r: Resumo) -> List[str]:
    cod = r.idioma
    partes: List[str] = []
    if r.lembretes_restantes:
        itens = [_item(i, cod) for i in r.lembretes_restantes]
        partes.append(texto("lembretes_restantes", cod, itens=_lista(itens, cod)))
    if r.compromissos_restantes:
        itens = [_item(i, cod) for i in r.compromissos_restantes]
        partes.append(texto("comp_restantes", cod, itens=_lista(itens, cod)))
    if r.pendencias_abertas:
        itens = _projeto_itens(r.pendencias_abertas, cod)
        partes.append(texto("proj_pendentes", cod, itens=_lista(itens, cod)))
    return partes


def escrever(r: Resumo) -> str:
    """O resumo completo: cabeçalho, seções com conteúdo e a frase final."""
    cod = r.idioma
    quando = _relativo(r.dia, r.agora)
    partes = [texto(f"cab_{quando}", cod, **_datas(r.dia))]
    secoes: List[str] = []
    if r.compromissos_feitos:
        itens = [_item(i, cod) for i in r.compromissos_feitos]
        secoes.append(texto("comp_feitos", cod, itens=_lista(itens, cod)))
    if r.compromissos_restantes:
        itens = [_item(i, cod) for i in r.compromissos_restantes]
        secoes.append(texto("comp_restantes", cod, itens=_lista(itens, cod)))
    if r.lembretes_feitos:
        secoes.append(
            texto("lembretes_feitos", cod, itens=_lista(r.lembretes_feitos, cod))
        )
    if r.lembretes_restantes:
        itens = [_item(i, cod) for i in r.lembretes_restantes]
        secoes.append(texto("lembretes_restantes", cod, itens=_lista(itens, cod)))
    if r.notas_total:
        chave = "notas_uma" if r.notas_total == 1 else "notas_varias"
        secoes.append(
            texto(
                chave,
                cod,
                n=r.notas_total,
                itens=texto("sep", cod).join(r.notas_ultimas),
            )
        )
    if r.organizacoes:
        itens = [
            texto("org_item_um" if n == 1 else "org_item", cod, pasta=p, n=n)
            for p, n in r.organizacoes
        ]
        secoes.append(texto("organizei", cod, itens=_lista(itens, cod)))
    if r.projetos_atualizados:
        secoes.append(
            texto("proj_atualizados", cod, itens=_lista(r.projetos_atualizados, cod))
        )
    if r.pendencias_concluidas:
        itens = _projeto_itens(r.pendencias_concluidas, cod)
        secoes.append(texto("proj_concluidas", cod, itens=_lista(itens, cod)))
    if r.pendencias_abertas:
        itens = _projeto_itens(r.pendencias_abertas, cod)
        secoes.append(texto("proj_pendentes", cod, itens=_lista(itens, cod)))
    partes += secoes or [texto("vazio", cod)]
    final = _frase_final(r)
    if final:
        partes.append(final)
    return " ".join(partes)


def escrever_pendente(r: Resumo) -> str:
    """Só o que ficou para depois: "o que ficou pendente hoje?"."""
    cod = r.idioma
    quando = _relativo(r.dia, r.agora)
    secoes = _secoes_pendentes(r)
    if secoes:
        partes = [texto(f"pcab_{quando}", cod, **_datas(r.dia)), *secoes]
    else:
        partes = [texto(f"pend_nada_{quando}", cod, **_datas(r.dia))]
    final = _frase_final(r)
    if final:
        partes.append(final)
    return " ".join(partes)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------


def montar(
    dia: Optional[date] = None,
    idioma: Optional[str] = None,
    *,
    agora: Optional[datetime] = None,
) -> Resumo:
    """O resumo de ``dia`` (hoje, sem ele) no ``idioma`` (português, sem ele)."""
    agora = agora or agora_local()
    dia = dia or agora.date()
    r = Resumo(dia=dia, idioma=codigo(idioma), agora=agora)

    compromissos = _seguro("agenda", lambda: _compromissos(dia), [])
    for c in compromissos:
        (r.compromissos_feitos if c.fim <= agora else r.compromissos_restantes).append(
            c.item()
        )
    seguinte = _seguro("agenda", lambda: _compromissos(dia + timedelta(days=1)), [])
    r.compromissos_seguinte = [c.item() for c in seguinte]
    r.lembretes_feitos, r.lembretes_restantes = _seguro(
        "lembretes", lambda: _lembretes(dia), ([], [])
    )
    notas_do_dia = _seguro("notas", lambda: _notas(dia, agora), [])
    r.notas_total = len(notas_do_dia)
    r.notas_ultimas = [_curta(n) for n in notas_do_dia[-ULTIMAS_NOTAS:]]
    r.organizacoes = _seguro("organização", lambda: _organizacoes(dia), [])
    (
        r.projetos_atualizados,
        r.pendencias_concluidas,
        r.pendencias_abertas,
    ) = _projetos(dia)
    r.texto = escrever(r)
    r.texto_pendente = escrever_pendente(r)
    return r


__all__ = [
    "Item",
    "Resumo",
    "agora_local",
    "escrever",
    "escrever_pendente",
    "hoje",
    "montar",
]
