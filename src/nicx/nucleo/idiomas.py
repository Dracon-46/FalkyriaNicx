"""Idiomas em que o Nicx conversa.

Uma tabela só para o app inteiro: o código que a interface manda
(``pt-BR``, ``en``...), o nome usado no pedido ao modelo, o código do
Whisper para ouvir e a voz do Kokoro para falar. O português é o padrão;
o modelo já responde nele pelo prompt de sistema, então só os outros
idiomas recebem uma instrução extra no fim da mensagem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PADRAO = "pt-BR"


@dataclass(frozen=True)
class Idioma:
    codigo: str
    nome: str
    whisper: str
    # Voz do Kokoro; vazio quando o Kokoro não fala o idioma (árabe).
    voz_kokoro: str


IDIOMAS: dict[str, Idioma] = {
    i.codigo: i
    for i in (
        Idioma("pt-BR", "português do Brasil", "pt", "pf_dora"),
        Idioma("en", "inglês (English)", "en", "af_heart"),
        Idioma("es", "espanhol (español)", "es", "ef_dora"),
        Idioma("zh", "chinês simplificado (简体中文)", "zh", "zf_xiaobei"),
        Idioma("hi", "hindi (हिन्दी)", "hi", "hf_alpha"),
        Idioma("ar", "árabe (العربية)", "ar", ""),
        Idioma("fr", "francês (français)", "fr", "ff_siwis"),
    )
}


def idioma(codigo: Optional[str]) -> Idioma:
    """O idioma do código (``"en"``, ``"pt"``, ``"es-MX"``...); senão, o padrão."""
    if codigo:
        codigo = codigo.strip()
        if codigo in IDIOMAS:
            return IDIOMAS[codigo]
        base = codigo.split("-")[0].lower()
        if base == "pt":
            return IDIOMAS[PADRAO]
        if base in IDIOMAS:
            return IDIOMAS[base]
    return IDIOMAS[PADRAO]


def instrucao_resposta(codigo: Optional[str]) -> str:
    """Texto para o fim da mensagem do usuário pedindo a resposta no idioma.

    Vazio para o português, que já é o idioma do prompt de sistema.
    """
    alvo = idioma(codigo)
    if alvo.codigo == PADRAO:
        return ""
    return (
        f"\n\n(Responda em {alvo.nome}, mesmo que as instruções estejam em português.)"
    )


__all__ = ["IDIOMAS", "PADRAO", "Idioma", "idioma", "instrucao_resposta"]
