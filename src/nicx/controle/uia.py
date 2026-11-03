"""Achar e acionar controles de uma janela pela UI Automation (.NET).

Usa o mesmo carregamento do :mod:`nicx.contexto.selecao` (pythonnet). Cada
operação roda numa thread com prazo: um app travado não trava o Nicx. Um
clique que abre uma caixa de diálogo pode deixar o ``Invoke`` esperando até
ela fechar; nesse caso o clique já aconteceu e a resposta diz isso.
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from nicx.acoes.intencoes import normalize

logger = logging.getLogger(__name__)

PRAZO_S = 5.0
ESPERA_CLIQUE_S = 1.5
MAX_ELEMENTOS = 600  # janelas enormes (navegador): o resto fica de fora

# tipo do UIA -> como o Nicx chama
TIPOS = {
    "Button": "botao",
    "SplitButton": "botao",
    "MenuItem": "menu",
    "TabItem": "aba",
    "CheckBox": "caixa",
    "RadioButton": "opcao",
    "Hyperlink": "link",
    "ListItem": "item",
    "TreeItem": "item",
    "ComboBox": "lista",
    "Edit": "campo",
}

# resultados de :func:`agir`
FEITO = "feito"
TALVEZ = "talvez"  # o app demorou a responder depois do clique (diálogo aberto)
NAO_ACHEI = "nao_achei"
DESATIVADO = "desativado"
NAO_CLICAVEL = "nao_clicavel"
SENHA = "senha"
JA_ESTAVA = "ja_estava"
DEMOROU = "demorou"
SEM_UIA = "sem_uia"


@dataclass(frozen=True)
class Elemento:
    nome: str
    tipo: str  # botao, menu, aba, caixa, opcao, link, item, lista, campo
    ativo: bool = True
    visivel: bool = True


@dataclass(frozen=True)
class Resultado:
    estado: str
    nome: str = ""
    tipo: str = ""
    # para "não achei": nomes parecidos ou os primeiros da janela
    sugestoes: tuple[str, ...] = ()


_T = TypeVar("_T")


def _com_prazo(funcao: Callable[[], _T], prazo: float, padrao: _T) -> _T:
    resultado: list[_T] = []

    def rodar() -> None:
        try:
            resultado.append(funcao())
        except Exception:  # noqa: BLE001
            logger.debug("UI Automation falhou", exc_info=True)

    thread = threading.Thread(target=rodar, name="nicx-controle-uia", daemon=True)
    thread.start()
    thread.join(prazo)
    if thread.is_alive():
        logger.info("A janela demorou demais para responder à acessibilidade")
    return resultado[0] if resultado else padrao


def _uia() -> Optional[dict[str, Any]]:
    if sys.platform != "win32":
        return None
    from nicx.contexto import selecao

    base = selecao._carregar_uia()
    if base is None:
        return None
    from System.Windows.Automation import (  # type: ignore[import-not-found]
        ExpandCollapsePattern,
        InvokePattern,
        OrCondition,
        SelectionItemPattern,
        TogglePattern,
        ValuePattern,
    )

    return {
        **base,
        "ExpandCollapsePattern": ExpandCollapsePattern,
        "InvokePattern": InvokePattern,
        "OrCondition": OrCondition,
        "SelectionItemPattern": SelectionItemPattern,
        "TogglePattern": TogglePattern,
        "ValuePattern": ValuePattern,
    }


def _tipo(elemento: Any) -> str:
    nome = str(elemento.Current.ControlType.ProgrammaticName).rsplit(".", 1)[-1]
    return TIPOS.get(nome, "")


def _brutos(uia: dict[str, Any], hwnd: int) -> list[Any]:
    elemento_cls = uia["AutomationElement"]
    tipos = uia["ControlType"]
    condicoes = [
        uia["PropertyCondition"](elemento_cls.ControlTypeProperty, getattr(tipos, t))
        for t in TIPOS
    ]
    raiz = elemento_cls.FromHandle(uia["IntPtr"](hwnd))
    achados = raiz.FindAll(uia["TreeScope"].Descendants, uia["OrCondition"](condicoes))
    return [achados[i] for i in range(min(achados.Count, MAX_ELEMENTOS))]


def _descrever(elemento: Any) -> Optional[Elemento]:
    atual = elemento.Current
    nome = " ".join(str(atual.Name or "").split())
    tipo = _tipo(elemento)
    if not nome or not tipo or len(nome) > 120:
        return None
    return Elemento(nome, tipo, bool(atual.IsEnabled), not bool(atual.IsOffscreen))


def listar(hwnd: int, prazo: float = PRAZO_S) -> Optional[list[Elemento]]:
    """Os controles com nome da janela (None: sem acessibilidade ou demorou)."""
    uia = _uia()
    if uia is None or not hwnd:
        return None

    def rodar() -> list[Elemento]:
        vistos: set[tuple[str, str]] = set()
        saida = []
        for bruto in _brutos(uia, hwnd):
            elemento = _descrever(bruto)
            if elemento is not None and (elemento.nome, elemento.tipo) not in vistos:
                vistos.add((elemento.nome, elemento.tipo))
                saida.append(elemento)
        return saida

    return _com_prazo(rodar, prazo, None)


def pontuar(alvo: str, elemento: Elemento, tipos: tuple[str, ...] = ()) -> int:
    """Quanto *elemento* parece ser o *alvo* (0 = nada). Nome igual ganha."""
    a, n = normalize(alvo), normalize(elemento.nome)
    if not a or not n:
        return 0
    n = n.rstrip(". ")  # "Salvar como..." -> "salvar como"
    if n == a:
        pontos = 100
    elif n.startswith(a + " ") or n.startswith(a):
        pontos = 70
    elif f" {a} " in f" {n} ":
        pontos = 50
    elif len(a) >= 4 and a in n:
        pontos = 30
    else:
        return 0
    if tipos and elemento.tipo in tipos:
        pontos += 15
    if elemento.visivel:
        pontos += 10
    if elemento.ativo:
        pontos += 5
    return pontos


def escolher(
    alvo: str, elementos: list[Elemento], tipos: tuple[str, ...] = ()
) -> Optional[int]:
    """Índice do melhor elemento para *alvo*, ou None."""
    melhor, indice = 0, None
    for i, elemento in enumerate(elementos):
        pontos = pontuar(alvo, elemento, tipos)
        if pontos > melhor:
            melhor, indice = pontos, i
    return indice


def _padrao(elemento: Any, classe: Any) -> Any:
    try:
        return elemento.GetCurrentPattern(classe.Pattern)
    except Exception:  # noqa: BLE001 - o controle não oferece esse padrão
        return None


def _acionar(uia: dict[str, Any], bruto: Any, op: str, texto: str, marca: list[str]):
    """Aciona *bruto*. ``marca`` recebe "clicando" antes de um Invoke."""
    if op == "digitar":
        if bool(bruto.Current.IsPassword):
            return SENHA
        valor = _padrao(bruto, uia["ValuePattern"])
        if valor is None or bool(valor.Current.IsReadOnly):
            return NAO_CLICAVEL
        valor.SetValue(texto)
        return FEITO
    if op in ("marcar", "desmarcar"):
        alternar = _padrao(bruto, uia["TogglePattern"])
        if alternar is None:
            return NAO_CLICAVEL
        ligado = str(alternar.Current.ToggleState).endswith("On")
        if ligado == (op == "marcar"):
            return JA_ESTAVA
        alternar.Toggle()
        return FEITO
    if op == "menu":
        expandir = _padrao(bruto, uia["ExpandCollapsePattern"])
        if expandir is not None:
            expandir.Expand()
            return FEITO
    if op == "aba" or _tipo(bruto) in ("aba", "item", "opcao"):
        selecionar = _padrao(bruto, uia["SelectionItemPattern"])
        if selecionar is not None:
            selecionar.Select()
            return FEITO
    invocar = _padrao(bruto, uia["InvokePattern"])
    if invocar is not None:
        marca.append("clicando")
        # Num app Win32, o Invoke só volta quando o diálogo ou menu que o
        # clique abriu fecha: não espera por isso.
        clique = threading.Thread(target=invocar.Invoke, daemon=True)
        clique.start()
        clique.join(ESPERA_CLIQUE_S)
        return FEITO if not clique.is_alive() else TALVEZ
    return _outros_padroes(uia, bruto)


def _outros_padroes(uia: dict[str, Any], bruto: Any) -> str:
    alternar = _padrao(bruto, uia["TogglePattern"])
    if alternar is not None:
        alternar.Toggle()
        return FEITO
    expandir = _padrao(bruto, uia["ExpandCollapsePattern"])
    if expandir is not None:
        expandir.Expand()
        return FEITO
    selecionar = _padrao(bruto, uia["SelectionItemPattern"])
    if selecionar is not None:
        selecionar.Select()
        return FEITO
    return NAO_CLICAVEL


# que tipo de controle cada operação procura primeiro
_TIPOS_DA_OP = {
    "clicar": ("botao", "link", "menu", "item"),
    "menu": ("menu",),
    "aba": ("aba",),
    "marcar": ("caixa", "opcao"),
    "desmarcar": ("caixa",),
    "digitar": ("campo", "lista"),
}


def achar(hwnd: int, op: str, alvo: str, prazo: float = PRAZO_S) -> Optional[Elemento]:
    """O controle que :func:`agir` acionaria, sem acionar."""
    elementos = listar(hwnd, prazo)
    if not elementos:
        return None
    indice = escolher(alvo, elementos, _TIPOS_DA_OP.get(op, ()))
    return elementos[indice] if indice is not None else None


def agir(
    hwnd: int, op: str, alvo: str, texto: str = "", prazo: float = PRAZO_S
) -> Resultado:
    """Acha *alvo* na janela e faz *op* (clicar, menu, aba, marcar, desmarcar,
    digitar)."""
    uia = _uia()
    if uia is None or not hwnd:
        return Resultado(SEM_UIA)
    escolhido: list[Elemento] = []
    marca: list[str] = []

    def rodar() -> Resultado:
        brutos, elementos = [], []
        for bruto in _brutos(uia, hwnd):
            elemento = _descrever(bruto)
            if elemento is not None:
                brutos.append(bruto)
                elementos.append(elemento)
        tipos = _TIPOS_DA_OP.get(op, ())
        indice = escolher(alvo, elementos, tipos)
        if indice is None:
            return Resultado(NAO_ACHEI, sugestoes=_sugestoes(alvo, elementos))
        elemento = elementos[indice]
        escolhido.append(elemento)
        if not elemento.ativo:
            return Resultado(DESATIVADO, elemento.nome, elemento.tipo)
        estado = _acionar(uia, brutos[indice], op, texto, marca)
        return Resultado(estado, elemento.nome, elemento.tipo)

    resultado = _com_prazo(rodar, prazo, None)
    if resultado is not None:
        return resultado
    if marca and escolhido:  # o Invoke ficou esperando: o clique já foi
        return Resultado(TALVEZ, escolhido[0].nome, escolhido[0].tipo)
    return Resultado(DEMOROU)


def _sugestoes(
    alvo: str, elementos: list[Elemento], limite: int = 8
) -> tuple[str, ...]:
    """Nomes que começam igual ao alvo; senão, os primeiros botões visíveis."""
    a = normalize(alvo)[:3]
    parecidos = [e.nome for e in elementos if a and normalize(e.nome).startswith(a)]
    if not parecidos:
        parecidos = [
            e.nome
            for e in elementos
            if e.visivel and e.tipo in ("botao", "menu", "aba")
        ]
    return tuple(dict.fromkeys(parecidos))[:limite]


__all__ = [
    "DEMOROU",
    "DESATIVADO",
    "FEITO",
    "JA_ESTAVA",
    "NAO_ACHEI",
    "NAO_CLICAVEL",
    "SEM_UIA",
    "SENHA",
    "TALVEZ",
    "Elemento",
    "Resultado",
    "achar",
    "agir",
    "escolher",
    "listar",
    "pontuar",
]
