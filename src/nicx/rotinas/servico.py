"""Rodar, criar, listar e apagar rotinas; o modelo pronto do modo foco.

Rodar uma rotina é executar cada passo com ``nicx.acoes.sistema.run``, como se
o usuário tivesse dito cada comando: a rotina foi criada por ele. Cada passo
vai para o histórico pelos ganchos de sempre, e a rotina inteira vira uma
linha "Rotina: nome".
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from nicx.acoes.intencoes import Action
from nicx.rotinas import armazenamento, textos
from nicx.rotinas.modelo import (
    PASSOS_PERMITIDOS,
    Passo,
    Rotina,
    RotinaInvalida,
    validar,
)
from nicx.rotinas.pedidos import normalizar_mesmo_tamanho
from nicx.rotinas.recorrencia import interpretar as interpretar_quando

_SEPARADORES = {
    "pt-BR": r"\s+e depois\s+|\s+depois\s+|\s+e\s+",
    "en": r"\s+and then\s+|\s+then\s+|\s+and\s+",
    "es": r"\s+y luego\s+|\s+luego\s+|\s+y\s+",
    "fr": r"\s+et puis\s+|\s+puis\s+|\s+et\s+",
}
_URL = re.compile(
    r"^(?:abre|abrir|abra|acessa|entra em|open|go to|abre la pagina|ouvre)\s+"
    r"(?:o site |the site |el sitio |le site )?"
    r"(?P<u>(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?)$",
    re.I,
)


def foco(idioma: Optional[str] = None) -> Rotina:
    """O modo foco pronto: fecha o WhatsApp, baixa o volume e marca 50 minutos."""
    return Rotina(
        nome=textos.texto("foco_nome", idioma),
        passos=[
            Passo("close", target="whatsapp"),
            Passo("volume", op="set", value=25),
            Passo("remind", target=textos.texto("foco_fim", idioma), minutos=50),
        ],
        frases=[],
        id="modelo-foco",
    )


def modelos(idioma: Optional[str] = None) -> list[Rotina]:
    return [foco(idioma)]


def interpretar_passos(
    texto: str, idioma: Optional[str] = None, agora: Optional[datetime] = None
) -> dict[str, Any]:
    """'abre o chrome, volume 30, toda segunda às 9h' -> passos e agenda.

    Também diz o que não entendeu e o que não pode ficar numa rotina.
    """
    from nicx.acoes import intencoes
    from nicx.acoes.textos import codigo

    cod = codigo(idioma)
    agora = agora or datetime.now()
    passos: list[Passo] = []
    agenda = None
    nao_entendi: list[str] = []
    proibidos: list[str] = []

    def um(trecho: str) -> Optional[tuple[str, Any]]:
        """O que o trecho é ("agenda", "passo", "proibido"), sem guardar nada."""
        norm = " ".join(normalizar_mesmo_tamanho(trecho).replace(",", " ").split())
        quando = interpretar_quando(norm)
        if quando is not None:
            return "agenda", quando
        m = _URL.match(trecho.strip())
        if m and "." in m.group("u"):
            url = m.group("u")
            alvo = url if url.lower().startswith("http") else f"https://{url}"
            return "passo", Passo("open_url", target=alvo)
        acao = intencoes.parse(trecho, cod)
        if acao is None:
            return None
        if acao.kind not in PASSOS_PERMITIDOS:
            return "proibido", trecho.strip()
        return "passo", Passo.de_acao(acao, agora)

    def guardar(itens: list[tuple[str, Any]]) -> None:
        nonlocal agenda
        for tipo, valor in itens:
            if tipo == "agenda":
                agenda = valor
            elif tipo == "passo":
                passos.append(valor)
            else:
                proibidos.append(valor)

    separador = _SEPARADORES.get(cod, _SEPARADORES["pt-BR"])
    for trecho in (t for t in re.split(r"[,;\n]+", texto) if t.strip()):
        inteiro = um(trecho)
        if inteiro is not None:
            guardar([inteiro])
            continue
        # "abre o chrome e o vs code": só vale dividir se todos os pedaços derem certo
        partes = [um(p) for p in re.split(separador, trecho) if p.strip()]
        if len(partes) > 1 and all(partes):
            guardar([p for p in partes if p])
            continue
        nao_entendi.append(trecho.strip())
    return {
        "passos": passos,
        "agenda": agenda,
        "nao_entendi": nao_entendi,
        "proibidos": proibidos,
    }


def executar(
    rotina: Rotina, origem: str = "app", idioma: Optional[str] = None
) -> tuple[bool, str]:
    """Roda os passos em ordem. Devolve (todos deram certo, frase para falar)."""
    from nicx.acoes import sistema
    from nicx.historico.registro import FALHOU, OK, anotar
    from nicx.historico.registro import origem as marcar_origem

    agora = datetime.now()
    feitas: list[str] = []
    falhas: list[str] = []
    detalhes = []
    with marcar_origem(origem):
        for passo in rotina.passos:
            saida = sistema.run(passo.para_acao(agora), idioma)
            (feitas if saida.ok else falhas).append(saida.message.rstrip("."))
            detalhes.append(
                {"passo": passo.kind, "ok": saida.ok, "resposta": saida.message[:200]}
            )
        ok = not falhas
        frase = textos.texto(
            "executada", idioma, nome=rotina.nome, passos=". ".join(feitas) + "."
        )
        if falhas:
            frase += textos.texto("falhas", idioma, lista="; ".join(falhas))
        anotar(
            "rotina",
            f"{rotina.nome}: {len(rotina.passos)}",
            detalhe={"rotina": rotina.id, "passos": detalhes},
            resultado=OK if ok else FALHOU,
        )
    if armazenamento.obter(rotina.id) is not None:
        armazenamento.marcar(
            rotina.id, ultima_execucao=agora.isoformat(timespec="seconds")
        )
    return ok, frase


def criar_por_frase(
    nome: str, resto: str, idioma: Optional[str] = None
) -> tuple[bool, str]:
    from nicx.acoes.textos import codigo

    if not resto.strip():
        return False, textos.texto("sem_passos", idioma)
    lido = interpretar_passos(resto, idioma)
    if lido["nao_entendi"]:
        return False, textos.texto(
            "nao_entendi", idioma, lista="; ".join(lido["nao_entendi"])
        )
    if lido["proibidos"]:
        return False, textos.texto(
            "proibidos", idioma, lista="; ".join(lido["proibidos"])
        )
    rotina = Rotina(
        nome=nome.strip(),
        passos=lido["passos"],
        agenda=lido["agenda"],
        idioma=codigo(idioma),
    )
    try:
        armazenamento.criar(validar(rotina))
    except RotinaInvalida:
        return False, textos.texto("sem_passos", idioma)
    except ValueError:
        return False, textos.texto("ja_existe", idioma, nome=rotina.nome)
    quando = ""
    if rotina.agenda:
        quando = textos.texto(
            "quando",
            idioma,
            dias=textos.dias(rotina.agenda.dias, idioma),
            hora=rotina.agenda.hora,
        )
    return True, textos.texto(
        "criada", idioma, nome=rotina.nome, n=len(rotina.passos), quando=quando
    )


def responder(acao: Action, idioma: Optional[str] = None):
    """Executa ``Action('rotina', op=...)`` e devolve o ``Outcome``."""
    from nicx.acoes.sistema import Outcome

    if acao.op == "criar":
        return Outcome(*criar_por_frase(acao.target, acao.site, idioma))
    if acao.op == "listar":
        rotinas = armazenamento.listar()
        if not rotinas:
            return Outcome(True, textos.texto("lista_vazia", idioma))
        return Outcome(
            True,
            textos.texto("lista", idioma, lista=", ".join(r.nome for r in rotinas)),
        )
    if acao.op == "apagar":
        alvo = armazenamento.por_frase(acao.target)
        if alvo is None:
            return Outcome(False, textos.texto("nao_achei", idioma, nome=acao.target))
        armazenamento.apagar(alvo.id)
        return Outcome(True, textos.texto("apagada", idioma, nome=alvo.nome))
    if acao.op == "foco":
        return Outcome(*executar(foco(idioma), idioma=idioma))
    rotina = armazenamento.obter(acao.target)
    if rotina is None:
        return Outcome(False, textos.texto("nao_achei", idioma, nome=acao.target))
    return Outcome(*executar(rotina, idioma=idioma))


__all__ = [
    "criar_por_frase",
    "executar",
    "foco",
    "interpretar_passos",
    "modelos",
    "responder",
]
