"""Decide se uma mensagem precisa das ferramentas do modelo.

Com o qwen3.5 no Ollama nada do prompt é reaproveitado entre perguntas: cada
token enviado é relido, a ~15-25 tokens/s na CPU. A lista de ferramentas
custa ~600 tokens; uma conversa comum ("e aí", "me explica X") não precisa
dela e responde em um terço do tempo sem ela.

Erra para o lado seguro: na dúvida, manda as ferramentas.
"""

from __future__ import annotations

import re
from typing import Iterable

from nicx.acoes.intencoes import normalize

_PATTERNS = [
    # Buscar fora: web, notícias, sites.
    r"\b(?:pesquis\w*|procur\w*|busc\w*|google|internet|na web|site|link|url|"
    r"noticia\w*|manchete\w*|wikipedia)\b",
    # Coisas que mudam com o tempo.
    r"\b(?:hoje|agora|ontem|amanha|atual\w*|ultim[oa]s?|recente\w*|esta semana|"
    r"este mes|este ano|202\d|preco\w*|cotac\w*|dolar|euro|bitcoin|bolsa|clima|"
    r"temperatura|chuva|previsao|placar|quem ganhou|eleic\w*|lancament\w*)\b",
    r"\b(?:como esta o tempo|tempo hoje|tempo amanha)\b",
    # Arquivos e o próprio computador.
    r"\b(?:arquivo\w*|pasta\w*|diretorio\w*|documento\w*|pdf|planilha\w*|csv|"
    r"txt|leia|ler o|ler a|abr[ae]\w*|execut\w*|rod[ae]\w*|comando\w*|terminal|"
    r"powershell|cmd|instal\w*|desinstal\w*|programa\w*|aplicativo\w*|volume|"
    r"som|musica|midia|tela|computador|pc|notebook|bateria|windows|processo\w*|"
    r"disco|memoria ram)\b",
    # Contas e código.
    r"\b(?:calcul\w*|vezes|dividido|porcentagem|raiz quadrada|potencia|python|"
    r"codigo|script|funcao|algoritmo|regex)\b",
    r"\d+\s*(?:[x*/+^-]|mais|menos)\s*\d+",
    r"\bferramenta\w*\b",
    # Rotinas: lembretes, anotações, print.
    r"\b(?:lembr\w*|avis[ae]r?|alarme|timer|temporizador|anot\w*|notas?|print"
    r"|captura)\b",
    # Agenda, arquivos, fotos e vídeos.
    r"\b(?:agenda\w*|compromisso\w*|reuniao|reunioes|calendar\w*|outlook|marca\w*"
    r"|desmarc\w*"
    r"|consulta|organiz\w*|arruma\w*|fotos?|imagens?|video\w*|youtube|toca\w*)\b",
    # Projetos (ferramenta ``projetos``).
    r"\b(?:projetos?|projects?|proyectos?|projets?|pendencias?|continuar"
    r"|onde (?:eu )?parei|left off|donde lo deje|ou j en etais)\b",
]
_REGEX = re.compile("|".join(f"(?:{p})" for p in _PATTERNS))


def needs_tools(text: str) -> bool:
    """True quando a mensagem parece pedir busca, dados atuais, PC ou contas.

    Inclui falar do que está na tela ("o que eu copiei", "isso aqui", "this
    page"): a ferramenta ``contexto`` lê a área de transferência e a janela.
    """
    if _REGEX.search(normalize(text or "")):
        return True
    from nicx.contexto.pedidos import menciona

    return menciona(text or "")


def needs_other_tools(text: str) -> bool:
    """Como ``needs_tools``, sem contar a referência à tela.

    Para pedidos cujo contexto já foi anexado à mensagem: "resume o que eu
    copiei" não precisa de ferramenta nenhuma; "anota o que eu copiei", sim.
    """
    return bool(_REGEX.search(normalize(text or "")))


def conversation_needs_tools(user_messages: Iterable[str]) -> bool:
    """Olha a última mensagem e a anterior do usuário.

    "Qual o clima hoje?" -> "Em qual cidade?" -> "Sorocaba": a resposta curta
    continua o pedido anterior, que precisava de busca.
    """
    recent = list(user_messages)[-2:]
    return any(needs_tools(text) for text in recent)
