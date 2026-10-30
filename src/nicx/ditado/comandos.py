"""Texto do ditado: comandos de voz simples e limpeza do que o Whisper escreveu.

Pontuação e maiúsculas são as do Whisper. Por cima disso, alguns comandos
falados viram caracteres, sempre em português e também no idioma escolhido:

- "nova linha" / "próxima linha" -> quebra de linha;
- "novo parágrafo" -> linha em branco;
- "ponto final" -> ``.``  (a palavra seguinte começa com maiúscula);
- "vírgula" -> ``,``.

O Whisper costuma pontuar o próprio comando ("tudo bem, vírgula, como vai");
essa pontuação extra é descartada. Nada aqui depende do sistema.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from nicx.nucleo.idiomas import PADRAO, idioma

LINHA = "linha"
PARAGRAFO = "paragrafo"
PONTO = "ponto"
VIRGULA = "virgula"


@dataclass(frozen=True)
class ComandosIdioma:
    frases: dict[str, tuple[str, ...]]
    ponto: str = "."
    virgula: str = ","
    # Escritas sem espaço entre palavras (chinês): o comando vale no meio.
    sem_fronteira: bool = False


COMANDOS: dict[str, ComandosIdioma] = {
    "pt-BR": ComandosIdioma(
        {
            LINHA: ("nova linha", "próxima linha"),
            PARAGRAFO: ("novo parágrafo",),
            PONTO: ("ponto final",),
            VIRGULA: ("vírgula",),
        }
    ),
    "en": ComandosIdioma(
        {
            LINHA: ("new line", "next line"),
            PARAGRAFO: ("new paragraph",),
            PONTO: ("full stop",),
            VIRGULA: ("comma",),
        }
    ),
    "es": ComandosIdioma(
        {
            LINHA: ("nueva línea", "siguiente línea"),
            PARAGRAFO: ("nuevo párrafo",),
            PONTO: ("punto final",),
            VIRGULA: ("coma",),
        }
    ),
    "fr": ComandosIdioma(
        {
            LINHA: ("nouvelle ligne", "à la ligne"),
            PARAGRAFO: ("nouveau paragraphe",),
            PONTO: ("point final",),
            VIRGULA: ("virgule",),
        }
    ),
    "zh": ComandosIdioma(
        {
            LINHA: ("换行",),
            PARAGRAFO: ("新段落",),
            PONTO: ("句号",),
            VIRGULA: ("逗号",),
        },
        ponto="。",
        virgula="，",
        sem_fronteira=True,
    ),
    "hi": ComandosIdioma(
        {
            LINHA: ("नई पंक्ति", "नई लाइन"),
            PARAGRAFO: ("नया अनुच्छेद",),
            PONTO: ("पूर्ण विराम",),
            VIRGULA: ("अल्पविराम",),
        },
        ponto="।",
    ),
    "ar": ComandosIdioma(
        {
            LINHA: ("سطر جديد",),
            PARAGRAFO: ("فقرة جديدة",),
            PONTO: ("نقطة",),
            VIRGULA: ("فاصلة",),
        },
        virgula="،",
    ),
}

# Pontuação que o Whisper põe em volta do comando falado.
_PONTUACAO = ",;:.!?…،，。।"
_FIM_DE_FRASE = ".!?…。।"

# Marcas internas: "próxima letra maiúscula" e "próxima letra minúscula".
_MAIUSCULA = "\x00"
_MINUSCULA = "\x01"

# Frases que o Whisper inventa sobre ruído (legendas de vídeos do treino).
_ALUCINACOES = frozenset(
    {
        "legendas pela comunidade amara.org",
        "legendas pela comunidade amara org",
        "subtitles by the amara.org community",
        "sous-titres réalisés para la communauté d'amara.org",
        "subtítulos realizados por la comunidad de amara.org",
    }
)


def _padrao_frase(frase: str) -> str:
    """Regex da frase tolerando acento faltando e espaço/hífen variável."""
    partes: list[str] = []
    for letra in frase:
        if letra.isspace():
            partes.append(r"[\s\-]+")
            continue
        base = unicodedata.normalize("NFD", letra)[0]
        if base != letra:
            partes.append(f"[{re.escape(letra)}{re.escape(base)}]")
        else:
            partes.append(re.escape(letra))
    return "".join(partes)


def _regex(cmds: ComandosIdioma) -> list[tuple[str, re.Pattern[str]]]:
    pont = re.escape(_PONTUACAO)
    lista: list[tuple[str, re.Pattern[str]]] = []
    for tipo, frases in cmds.frases.items():
        alternativas = "|".join(
            _padrao_frase(f) for f in sorted(frases, key=len, reverse=True)
        )
        if cmds.sem_fronteira:
            nucleo = f"(?:{alternativas})"
        else:
            nucleo = rf"(?<!\w)(?:{alternativas})(?!\w)"
        padrao = (
            rf"(?P<antes>[ \t]*[{pont}]?[ \t]*)"
            + nucleo
            # Só leva os espaços junto se vier pontuação depois do comando.
            + rf"(?P<depois>(?:[ \t]*[{pont}]+)?)"
        )
        lista.append((tipo, re.compile(padrao, re.IGNORECASE)))
    return lista


def _substituir(tipo: str, cmds: ComandosIdioma, m: re.Match[str]) -> str:
    antes = m.group("antes").strip()
    depois = m.group("depois").strip()
    if tipo in (LINHA, PARAGRAFO):
        # Mantém o fim de frase que veio antes ("Obrigado. Nova linha.").
        manter = antes if antes and antes in _FIM_DE_FRASE else ""
        quebra = "\n" if tipo == LINHA else "\n\n"
        return manter + quebra + _MAIUSCULA
    if tipo == PONTO:
        return cmds.ponto + _MAIUSCULA
    # Vírgula: se o Whisper achou que a frase acabou ali, a próxima palavra
    # não é começo de frase.
    marca = _MINUSCULA if depois and depois[-1] in _FIM_DE_FRASE else ""
    return cmds.virgula + marca


def _caixa(texto: str) -> str:
    def maiuscula(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2).upper()

    def minuscula(m: re.Match[str]) -> str:
        palavra = m.group(2)
        # Siglas ("ONU") ficam como estão.
        if len(palavra) > 1 and palavra[1:].isupper():
            return m.group(1) + palavra
        return m.group(1) + palavra[0].lower() + palavra[1:]

    texto = re.sub(_MAIUSCULA + r"(\s*)(\w)", maiuscula, texto)
    texto = re.sub(_MINUSCULA + r"(\s*)(\w+)", minuscula, texto)
    return texto.replace(_MAIUSCULA, "").replace(_MINUSCULA, "")


def comandos_para(codigo: Optional[str]) -> list[ComandosIdioma]:
    """Comandos em português e no idioma *codigo* (sem repetir)."""
    alvo = idioma(codigo).codigo
    codigos = [PADRAO] if alvo == PADRAO else [alvo, PADRAO]
    return [COMANDOS[c] for c in codigos if c in COMANDOS]


def aplicar_comandos(texto: str, codigo: Optional[str] = None) -> str:
    for cmds in comandos_para(codigo):
        for tipo, regex in _regex(cmds):
            texto = regex.sub(lambda m, t=tipo, c=cmds: _substituir(t, c, m), texto)
    return _caixa(texto)


def limpar(texto: str) -> str:
    """Tira espaços sobrando (mantém as quebras de linha dos comandos)."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t ]+([,.，。،।])", r"\1", texto)
    texto = re.sub(r"[ \t ]{2,}", " ", texto)
    texto = re.sub(r"[ \t ]*\n[ \t ]*", "\n", texto)
    return texto.strip(" \t ")


def _alucinacao(texto: str) -> bool:
    return texto.strip().rstrip(".!").lower() in _ALUCINACOES


def preparar_texto(bruto: str, codigo: Optional[str] = None) -> str:
    """Do texto do Whisper ao que será digitado; vazio = não digitar nada.

    Sem nenhuma letra ou número (só ruído, pontuação solta) ou uma alucinação
    conhecida do Whisper: vazio.
    """
    if not bruto or not any(c.isalnum() for c in bruto) or _alucinacao(bruto):
        return ""
    texto = limpar(aplicar_comandos(limpar(bruto), codigo))
    if not texto.strip() and "\n" not in texto:
        return ""
    return texto


__all__ = [
    "COMANDOS",
    "ComandosIdioma",
    "aplicar_comandos",
    "comandos_para",
    "limpar",
    "preparar_texto",
]
