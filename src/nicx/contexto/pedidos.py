"""Reconhece pedidos sobre o que o usuário está vendo.

- ``area_transferencia``: "resume o que eu copiei", "corrige o texto copiado",
  "translate what I copied", "traduce lo que copié", "résume ce que j'ai copié";
- ``janela``: "explica isso aqui", "o que é esse erro?", "resume essa
  página", "summarize this page", "explica esto", "explique cette page";
- ``onde``: "onde eu tô?", "where am I?", "¿dónde estoy?", "où suis-je ?".

Português, inglês, espanhol e francês são aceitos sempre (as frases não se
confundem). "Traduz isso" sozinho (sem "aqui", sem "essa página") só conta
na primeira mensagem da conversa ou por voz: no meio de uma conversa, "isso"
costuma ser a resposta anterior do Nicx. Se a própria mensagem já traz o
texto ("traduz isso: hello world"), não é pedido de contexto.

Não são ações rápidas: o Nicx junta o texto e manda ao modelo
(:mod:`nicx.contexto.servico`). Só "onde eu tô?" responde direto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from nicx.acoes.intencoes import normalize

AREA = "area_transferencia"
JANELA = "janela"
ONDE = "onde"


@dataclass(frozen=True)
class Pedido:
    fonte: str  # AREA | JANELA | ONDE
    resto: str  # a mensagem (normalizada) sem a referência ao contexto


def _juntar(*padroes: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in padroes))


# --- Área de transferência -------------------------------------------------
_AREA = _juntar(
    # pt
    r"\b(?:(?:o|oq|aquilo|isso|esse texto|o texto|o trecho|o link)\s+)?"
    r"(?:que\s+)?(?:eu\s+)?(?:acabei de copiar|copiei|tinha copiado)\b",
    r"\b(?:texto|trecho|conteudo|link|codigo|erro)\s+copiad[oa]s?\b",
    r"\b(?:o que|oq)\s+(?:ta|esta|tem)\s+(?:copiado|na area de transferencia)\b",
    r"\b(?:minha\s+|na\s+|da\s+)?area de transferencia\b",
    r"\bclipboard\b",
    r"\bdo ctrl\s*c\b",
    # en
    r"\b(?:what\s+)?i(?: just| have)? copied\b",
    r"\b(?:the\s+)?copied (?:text|stuff|code|error|link)\b",
    # es
    r"\blo que (?:he copiado|copie|acabo de copiar)\b",
    r"\b(?:he copiado|acabo de copiar)\b",
    r"\b(?:el\s+)?(?:texto|codigo|enlace) copiado\b",
    r"\b(?:del\s+|el\s+)?portapapeles\b",
    # fr
    r"\b(?:ce que\s+)?j ai copie\b",
    r"\b(?:le\s+)?texte copie\b",
    r"\b(?:du\s+|le\s+)?presse[- ]papiers?\b",
)

# --- Janela aberta ---------------------------------------------------------
_COISAS_F_PT = (
    r"pagina|janela|tela|aba|planilha|apresentacao|mensagem|noticia|"
    r"materia|tabela|funcao|classe|linha|frase|secao|pergunta|questao"
)
_COISAS_M_PT = (
    r"erro|documento|arquivo|codigo|texto|e ?mail|email|site|pdf|trecho|"
    r"paragrafo|artigo|aviso|alerta|script|log|contrato|relatorio|programa|"
    r"exercicio|slide|video"
)
_JANELA = _juntar(
    # pt
    r"\b(?:isso|isto|esse|essa|este|esta)\s+(?:aqui|ai|daqui)\b",
    rf"\b(?:nessa|nesta|dessa|desta|essa|esta)\s+(?:{_COISAS_F_PT})\b",
    rf"\b(?:nesse|neste|desse|deste|esse|este)\s+(?:{_COISAS_M_PT})\b",
    r"\b(?:o que|oq|o texto que|o trecho que)\s+(?:eu\s+)?"
    r"(?:selecionei|marquei|destaquei)\b",
    r"\btexto selecionado\b",
    r"\b(?:o que|oq)\s+(?:ta|esta|aparece)\s+na (?:minha )?tela\b",
    r"\bna minha tela\b",
    # en
    r"\b(?:this|that)\s+(?:right\s+)?here\b",
    r"\b(?:this|that)\s+(?:page|window|screen|tab|document|doc|file|error|"
    r"e ?mail|email|code|text|message|pdf|article|spreadsheet|sheet|site|"
    r"website|function|paragraph|warning|section|slide|question|exercise)\b",
    r"\bwhat i (?:selected|highlighted)\b",
    r"\b(?:the\s+)?selected text\b",
    r"\bon my screen\b",
    # es
    r"\b(?:esto|eso)\s+(?:de\s+)?aqui\b",
    r"\b(?:esta|esa)\s+(?:pagina|ventana|pantalla|pestana|hoja|tabla|funcion|"
    r"pregunta|seccion)\b",
    r"\b(?:este|ese)\s+(?:error|documento|archivo|codigo|texto|correo|mensaje|"
    r"sitio|pdf|articulo|parrafo|aviso)\b",
    r"\blo que (?:he\s+)?seleccion(?:e|ado)\b",
    r"\ben mi pantalla\b",
    # fr
    r"\b(?:ceci|ca|cela)\s+(?:ici|la)\b",
    r"\bcette\s+(?:page|fenetre|erreur|feuille|fonction|phrase|section|question)\b",
    r"\b(?:ce|cet)\s+(?:document|fichier|code|texte|e ?mail|email|site|pdf|"
    r"article|paragraphe|message|onglet|ecran|avertissement)\b",
    r"\bce que j ai selectionne\b",
    r"\btexte selectionne\b",
    r"\bsur mon ecran\b",
)
# "Traduz isso", "explain this": só na primeira mensagem ou por voz.
_VERBOS = (
    # pt
    r"resum[aeio]r?|resumi|traduz[aei]?r?|explic[aq]u?e?r?|corrig[ea]r?|corrij[ao]|"
    r"revis[ae]r?|respond[ae]r?|le|leia|ler|reescrev[ae]r?|melhor[ae]r?|"
    r"analis[ae]r?|coment[ae]r?|"
    # en
    r"summari[sz]e|translate|explain|fix|correct|proofread|answer|reply to|"
    r"rewrite|read|review|check|"
    # es
    r"resume(?:me)?|traduce(?:me)?|explica(?:me)?|corrige|revisa|responde|"
    r"reescribe|lee|analiza|"
    # fr
    r"resume|traduis|traduire|explique|expliquer|corrige|relis|reponds|"
    r"reecris|lis|analyse"
)
_PRONOMES = r"isso|isto|this|that|it|esto|eso|ceci|ca|cela"
_ISSO_SOLTO = re.compile(rf"^(?:{_VERBOS})\s+(?:{_PRONOMES})\b")
_PRONOME = re.compile(rf"\b(?:{_PRONOMES})\b")
_O_QUE_E_ISSO = re.compile(
    r"^(?:o que e isso|o que significa isso|what is this|what does this mean|"
    r"que es esto|qu est ce que c est|c est quoi)\b"
)

# --- Onde eu estou ---------------------------------------------------------
_ONDE = re.compile(
    r"^(?:(?:onde|aonde) (?:eu )?(?:to|estou|esto)|"
    r"em que (?:app|aplicativo|programa|janela|arquivo|pagina|site)"
    r" (?:eu )?(?:to|estou)|"
    r"que (?:janela|app|aplicativo|programa|arquivo|pagina) (?:e essa|e esse|"
    r"ta aberta|ta aberto|esta aberta|esta aberto)|"
    r"qual (?:janela|app|aplicativo|programa|arquivo) (?:ta|esta) aberto|"
    r"where am i|what (?:app|window|file|program|page)"
    r" (?:is this|am i (?:in|on|using))|"
    r"which (?:app|window|file) am i (?:in|on)|"
    r"(?:donde|en donde) estoy|"
    r"en que (?:app|aplicacion|ventana|programa|archivo) estoy|"
    r"ou suis je|ou je suis|dans quel(?:le)? (?:app|application|fenetre|fichier|"
    r"programme|page) (?:suis je|je suis))$"
)
_CORTESIA = re.compile(
    r"^(?:(?:ei|oi|ok|ola|hey|hi|oye|hola|salut)\s+)?(?:nicx|nix|nics)?\s*"
    r"(?:(?:por favor|pfv|please|s il te plait|s il vous plait)\s+)?"
    r"(?:(?:pode|poderia|consegue|voce pode|da pra|can you|could you|puedes|"
    r"podrias|peux tu|pourrais tu)\s+)?"
)


def _tem_texto_proprio(original: str) -> bool:
    """A mensagem já traz o conteúdo ("traduz isso: hello world")."""
    original = (original or "").strip()
    if len(original) > 400 or "\n" in original:
        return True
    return bool(re.search(r"[:\"“«]\s*\S.{14,}", original))


def _sem(texto: str, padrao: re.Pattern[str]) -> str:
    return re.sub(r"\s+", " ", padrao.sub(" ", texto)).strip()


def detectar(texto: str, *, primeira: bool = True) -> Optional[Pedido]:
    """O pedido de contexto em *texto*, ou None.

    *primeira*: a mensagem abre a conversa (ou veio por voz). Só então
    "traduz isso" sozinho vale como pedido sobre a tela.
    """
    original = texto or ""
    # "où suis-je", "presse-papiers": o hífen vira espaço.
    norma = normalize(original).replace("-", " ")
    if not norma:
        return None
    sem_cortesia = _CORTESIA.sub("", norma).strip()
    if _ONDE.match(sem_cortesia.rstrip(" ?")):
        return Pedido(ONDE, "")
    if _AREA.search(norma):
        return Pedido(AREA, _sem(norma, _AREA))
    if _tem_texto_proprio(original):
        return None
    if _JANELA.search(norma):
        return Pedido(JANELA, _sem(norma, _JANELA))
    if primeira and (
        _ISSO_SOLTO.match(sem_cortesia) or _O_QUE_E_ISSO.match(sem_cortesia)
    ):
        return Pedido(JANELA, _sem(sem_cortesia, _PRONOME))
    return None


def menciona(texto: str) -> bool:
    """Qualquer referência ao que está na tela (para o roteamento de
    ferramentas, que erra para o lado de mandar)."""
    return detectar(texto, primeira=True) is not None


__all__ = ["AREA", "JANELA", "ONDE", "Pedido", "detectar", "menciona"]
