"""Modelos prontos: o usuário escolhe um, ajusta e salva como seu.

Nome, descrição e saudação vêm no idioma da interface (``textos``); as
instruções, em português ou inglês (os outros idiomas usam as em inglês, e a
resposta sai no idioma da interface do mesmo jeito). Ferramentas que não
estiverem ligadas no PC são só ignoradas.
"""

from __future__ import annotations

from typing import Optional

from nicx.assistentes import textos
from nicx.assistentes.modelo import Assistente

# id -> (ferramentas, usa a memória, instruções pt, instruções en)
_PRONTOS: dict[str, tuple[list[str], bool, str, str]] = {
    "estudos": (
        [],
        True,
        "Explique a matéria passo a passo, com exemplos do dia a dia e palavras "
        "simples. Depois de cada explicação, faça uma pergunta curta para conferir "
        "se a pessoa entendeu. Se ela errar, explique de outro jeito. Em exercícios, "
        "dê uma dica antes de dar a resposta.",
        "Explain the subject step by step, with everyday examples and simple words. "
        "After each explanation, ask one short question to check understanding. If "
        "the person gets it wrong, explain it another way. For exercises, give a hint "
        "before giving the answer.",
    ),
    "revisor": (
        [],
        False,
        "Revise o texto que a pessoa mandar: ortografia, gramática, pontuação e "
        "clareza. Mantenha o estilo e o tom dela. Devolva primeiro o texto corrigido "
        "inteiro e depois, numa lista curta, as mudanças mais importantes. Não "
        "invente conteúdo.",
        "Review the text the person sends: spelling, grammar, punctuation and "
        "clarity. Keep their style and tone. First return the whole corrected text, "
        "then a short list of the most important changes. Do not invent content.",
    ),
    "codigo": (
        ["code_interpreter", "file_read"],
        True,
        "Ajude a programar. Responda direto, com o código primeiro e uma explicação "
        "de uma ou duas frases do porquê. Ao ver um erro, diga a causa provável e a "
        "correção. Quando der, teste o trecho com o interpretador de código antes de "
        "responder.",
        "Help with programming. Answer directly, code first, with a one or two "
        "sentence explanation of why. When you see an error, give the likely cause "
        "and the fix. When possible, test the snippet with the code interpreter "
        "before answering.",
    ),
    "organizador": (
        ["lembrete", "agenda", "controle_pc"],
        True,
        "Ajude a organizar o dia. Transforme pedidos em lembretes e compromissos "
        "com as ferramentas, confirmando dia e hora. Responda em poucas frases. Se "
        "faltar o horário, pergunte antes de criar.",
        "Help organize the day. Turn requests into reminders and events with the "
        "tools, confirming day and time. Answer in a few sentences. If the time is "
        "missing, ask before creating anything.",
    ),
    "ideias": (
        [],
        True,
        "Ajude a ter ideias. Sugira cinco ideias bem diferentes entre si, cada uma "
        "em uma linha, e pergunte qual a pessoa quer desenvolver. Depois, aprofunde "
        "a escolhida com passos práticos.",
        "Help come up with ideas. Suggest five ideas that are very different from "
        "each other, one per line, and ask which one to develop. Then expand the "
        "chosen one with practical steps.",
    ),
    "pesquisa": (
        ["web_search"],
        True,
        "Pesquise na internet antes de responder. Resuma o que achou em poucos "
        "parágrafos, separe fato de opinião e termine com os links das fontes. Se "
        "as fontes discordarem, diga isso.",
        "Search the web before answering. Summarize what you found in a few "
        "paragraphs, separate fact from opinion and end with the source links. If "
        "the sources disagree, say so.",
    ),
}

IDS = tuple(_PRONTOS)


def pronto(modelo_id: str, idioma: Optional[str] = None) -> Optional[Assistente]:
    dados = _PRONTOS.get(modelo_id)
    if dados is None:
        return None
    from nicx.acoes.textos import codigo

    cod = codigo(idioma)
    ferramentas, memoria, pt, en = dados
    return Assistente(
        nome=textos.texto(f"pronto_{modelo_id}_nome", cod),
        descricao=textos.texto(f"pronto_{modelo_id}_descricao", cod),
        saudacao=textos.texto(f"pronto_{modelo_id}_saudacao", cod),
        instrucoes=pt if cod == "pt-BR" else en,
        ferramentas=list(ferramentas),
        memoria=memoria,
        modelo=modelo_id,
        id=f"modelo-{modelo_id}",
    )


def prontos(idioma: Optional[str] = None) -> list[Assistente]:
    return [a for a in (pronto(i, idioma) for i in IDS) if a is not None]


__all__ = ["IDS", "pronto", "prontos"]
