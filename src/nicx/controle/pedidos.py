"""Frases que pedem para mexer num controle da janela.

Recebe o texto já limpo pelas ações rápidas (minúsculas, sem acento, sem as
gentilezas em volta) e o mapa para o texto original, de onde sai o que
digitar com as maiúsculas e os acentos do usuário. Português, inglês,
espanhol e francês valem sempre: as frases não se confundem.

Só verbos de clique ("clica", "click", "haz clic", "clique sur") viram
clique sem mais nada; "aperta"/"press" exigem a palavra botão, para "aperta
o play" continuar sendo mídia.
"""

from __future__ import annotations

import re
from typing import Optional

from nicx.acoes.intencoes import Action, original_text

KIND = "ui"

_ARTIGO = r"(?:(?:em|no|na|nos|nas|o|a|os|as|sobre|the|on|en|el|la|le|les|sur|l)\s+)*"
_TIPO_PT = r"(?:(?:botao|link|opcao|item|icone)\s+(?:de\s+|do\s+|da\s+)?)?"
_TIPO_EN = r"(?:(?:button|link|option|item|icon)\s+)?"
_TIPO_ES = r"(?:(?:boton|enlace|opcion)\s+(?:de\s+)?)?"
_TIPO_FR = r"(?:(?:bouton|lien|option)\s+)?"
_FIM_TIPO = r"(?:\s+(?:button|link|botao|boton|bouton))?"

_REGRAS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (op, re.compile(padrao))
    for op, padrao in (
        # --- listar
        (
            "listar",
            r"^(?:o que|oq)\s+(?:da|posso|eu posso|consigo|tem)\s+(?:pra\s+|para\s+)?"
            r"(?:clicar|apertar)(?:\s+(?:aqui|ai|nessa janela))?$",
        ),
        (
            "listar",
            r"^quais\s+(?:sao\s+)?(?:os\s+)?(?:botoes|opcoes)\s*(?:tem\s*)?"
            r"(?:aqui|ai|nessa janela|dessa janela)?$",
        ),
        ("listar", r"^what can i click(?: on)?(?: here)?$"),
        ("listar", r"^(?:which|what) buttons are (?:there|here)$"),
        ("listar", r"^que puedo (?:pulsar|hacer clic)(?: aqui)?$"),
        ("listar", r"^sur quoi (?:je peux|puis je) cliquer(?: ici)?$"),
        # --- digitar ("escreve X no campo Y")
        (
            "digitar",
            r"^(?:escreve|escreva|digita|digite|preenche|preencha|coloca|coloque)\s+"
            r"(?P<texto>.+?)\s+(?:no|na|em)\s+(?:campo|caixa)\s+(?:de\s+|do\s+|da\s+)?"
            r"(?P<alvo>.+)$",
        ),
        (
            "digitar",
            r"^(?:type|write|enter)\s+(?P<texto>.+?)\s+in(?:to)?\s+the\s+"
            r"(?P<alvo>.+?)\s+(?:field|box)$",
        ),
        (
            "digitar",
            r"^(?:escribe|teclea)\s+(?P<texto>.+?)\s+en\s+el\s+campo\s+(?:de\s+)?"
            r"(?P<alvo>.+)$",
        ),
        (
            "digitar",
            r"^(?:ecris|tape|saisis)\s+(?P<texto>.+?)\s+dans\s+le\s+champ\s+"
            r"(?P<alvo>.+)$",
        ),
        # --- menu
        (
            "menu",
            r"^(?:abre|abra|abrir)\s+o\s+menu\s+(?:de\s+|do\s+|da\s+)?(?P<alvo>.+)$",
        ),
        ("menu", r"^open\s+the\s+(?P<alvo>.+?)\s+menu$"),
        ("menu", r"^(?:abre|abrir)\s+el\s+menu\s+(?:de\s+)?(?P<alvo>.+)$"),
        ("menu", r"^(?:ouvre|ouvrir)\s+le\s+menu\s+(?P<alvo>.+)$"),
        # --- aba
        (
            "aba",
            r"^(?:vai|va|ir|muda|mude|troca|troque|seleciona|selecione|abre|abra)\s+"
            r"(?:para\s+|pra\s+|na\s+|pra\s+a\s+|para\s+a\s+|a\s+)?aba\s+"
            r"(?:de\s+|do\s+|da\s+)?(?P<alvo>.+)$",
        ),
        ("aba", r"^(?:go to|switch to|open|select)\s+the\s+(?P<alvo>.+?)\s+tab$"),
        ("aba", r"^(?:ve|ir|cambia)\s+a\s+la\s+pestana\s+(?:de\s+)?(?P<alvo>.+)$"),
        ("aba", r"^(?:va|aller)\s+(?:a|sur)\s+l\s+onglet\s+(?P<alvo>.+)$"),
        # --- marcar / desmarcar
        (
            "desmarcar",
            r"^(?:desmarca|desmarque|desmarcar|desativa|desative|desliga|desligue)\s+"
            r"(?:a\s+|o\s+)?(?:caixa|caixinha|opcao)\s+(?:de\s+|do\s+|da\s+)?"
            r"(?P<alvo>.+)$",
        ),
        (
            "marcar",
            r"^(?:marca|marque|marcar|ativa|ative|liga|ligue)\s+"
            r"(?:a\s+|o\s+)?(?:caixa|caixinha|opcao)\s+(?:de\s+|do\s+|da\s+)?"
            r"(?P<alvo>.+)$",
        ),
        (
            "desmarcar",
            r"^uncheck\s+(?:the\s+)?(?P<alvo>.+?)\s+(?:box|checkbox|option)$",
        ),
        (
            "marcar",
            r"^(?:check|tick)\s+(?:the\s+)?(?P<alvo>.+?)\s+(?:box|checkbox|option)$",
        ),
        ("desmarcar", r"^desmarca\s+(?:la\s+)?casilla\s+(?:de\s+)?(?P<alvo>.+)$"),
        ("marcar", r"^marca\s+(?:la\s+)?casilla\s+(?:de\s+)?(?P<alvo>.+)$"),
        ("desmarcar", r"^decoche\s+(?:la\s+)?case\s+(?P<alvo>.+)$"),
        ("marcar", r"^coche\s+(?:la\s+)?case\s+(?P<alvo>.+)$"),
        # --- clicar
        (
            "clicar",
            rf"^(?:clica|clique|clicar|da um clique)\s+{_ARTIGO}{_TIPO_PT}"
            r"(?P<alvo>.+)$",
        ),
        (
            "clicar",
            r"^(?:aperta|aperte|apertar|pressiona|pressione)\s+(?:o\s+)?botao\s+"
            r"(?:de\s+|do\s+|da\s+)?(?P<alvo>.+)$",
        ),
        ("clicar", rf"^click\s+{_ARTIGO}{_TIPO_EN}(?P<alvo>.+?){_FIM_TIPO}$"),
        ("clicar", r"^press\s+the\s+(?P<alvo>.+?)\s+button$"),
        ("clicar", rf"^haz\s+clic\s+{_ARTIGO}{_TIPO_ES}(?P<alvo>.+?){_FIM_TIPO}$"),
        ("clicar", r"^pulsa\s+el\s+boton\s+(?:de\s+)?(?P<alvo>.+)$"),
        ("clicar", rf"^clique\s+sur\s+{_ARTIGO}{_TIPO_FR}(?P<alvo>.+?){_FIM_TIPO}$"),
        ("clicar", r"^appuie\s+sur\s+(?:le\s+)?bouton\s+(?P<alvo>.+)$"),
    )
)
_SOBRA = re.compile(
    r"\s+(?:aqui|ai|nessa janela|nesta janela|na janela|pra mim|here|in this window|"
    r"aqui mismo|ici)$"
)


def parse(text: str, t: str, where: list[int]) -> Optional[Action]:
    """O pedido em *t* (texto limpo de *text*), ou None.

    ``Action("ui", op, target=alvo, site=texto)``: *op* é listar, clicar, menu,
    aba, marcar, desmarcar ou digitar; *site* só leva o que digitar.
    """
    if not t:
        return None
    for op, padrao in _REGRAS:
        achado = padrao.match(t)
        if achado is None:
            continue
        if op == "listar":
            return Action(KIND, "listar")
        alvo = _SOBRA.sub("", achado.group("alvo")).strip()
        if not alvo or len(alvo) > 80:
            return None
        if op == "digitar":
            inicio, fim = achado.span("texto")
            digitar = original_text(text, where, inicio, fim)
            return Action(KIND, op, target=alvo, site=digitar)
        return Action(KIND, op, target=alvo)
    return None


__all__ = ["KIND", "parse"]
