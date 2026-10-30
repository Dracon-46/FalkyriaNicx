# ruff: noqa: E501  (tabela de padrões: um por linha fica mais legível)
"""Reconhece os pedidos sobre projetos (português, inglês, espanhol, francês).

- ``criar``: "cria o projeto Site Novo (na pasta C:\\dev\\site)";
- ``listar``: "quais meus projetos?", "list my projects";
- ``ver``: "como está o projeto Lumen?", "how is project Lumen going?";
- ``falta``: "o que falta no projeto Lumen?";
- ``decisao``: "anota no projeto Lumen que decidimos usar Postgres",
  "decisão no projeto Lumen: usar Postgres";
- ``pendencia``: "adiciona pendência no projeto Lumen: comprar o domínio";
- ``concluir``: "conclui a pendência comprar o domínio do projeto Lumen";
- ``estado``: "atualiza o estado do projeto Lumen: API pronta";
- ``arquivar``, ``renomear``;
- ``continuar``: "continue de onde parei", "o que eu estava fazendo?",
  "pick up where I left off", "reprends où j'en étais"... "Vamos continuar"
  sozinho só conta na primeira mensagem da conversa (no meio dela, é a
  conversa que continua).

Os quatro idiomas valem sempre (as frases não se confundem). Chinês, hindi e
árabe: só a frase de continuar que a página Projetos manda.

Tudo aqui é texto: quem resolve o projeto e executa é :mod:`.servico`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from nicx.acoes.intencoes import clean_with_map, normalize, original_text

CRIAR = "criar"
LISTAR = "listar"
VER = "ver"
FALTA = "falta"
DECISAO = "decisao"
PENDENCIA = "pendencia"
CONCLUIR = "concluir"
ESTADO = "estado"
ARQUIVAR = "arquivar"
RENOMEAR = "renomear"
CONTINUAR = "continuar"

MAX_CARACTERES = 600


@dataclass(frozen=True)
class Pedido:
    tipo: str
    nome: str = ""  # como o usuário escreveu; vazio = projeto atual
    texto: str = ""  # decisão, pendência, estado
    pasta: str = ""  # criar: "na pasta ..."
    novo_nome: str = ""  # renomear
    # O nome veio grudado no texto ("no projeto Lumen comprar domínio"):
    # quem resolve separa pelo nome de um projeto que existe.
    junto: bool = False


def _c(padrao: str) -> re.Pattern[str]:
    return re.compile(padrao)


_P = r"(?:projeto|project|proyecto|projet)"
_EM = (
    r"(?:no|ao|pro|para o|do|em|in|on|to|for|of|en el|al|del|para el|dans le|au|du"
    r"|sur le)"
)
_O = r"(?:(?:o|a|the|el|le|um|uma|a|an|un|une) )?"

# --- Frase inteira -----------------------------------------------------------
_FRASES: list[tuple[str, re.Pattern[str]]] = [
    # Listar
    (
        LISTAR,
        _c(
            r"(?:quais (?:sao )?(?:os )?meus projetos|(?:lista|listar|liste|mostra|mostre"
            r"|mostrar|ver) (?:os |todos os )?(?:meus )?projetos|meus projetos"
            r"|(?:que|quais) projetos (?:eu )?tenho"
            r"|(?:what are|which are|show|show me|list) (?:all )?(?:of )?my projects"
            r"|my projects|what projects do i have"
            r"|(?:cuales son|muestra|muestrame|lista|listar) (?:todos )?mis proyectos"
            r"|mis proyectos|que proyectos tengo"
            r"|(?:quels sont|montre|montre-moi|liste) (?:tous )?mes projets|mes projets"
            r"|quels projets (?:ai-je|j ai))"
        ),
    ),
    # Criar
    (
        CRIAR,
        _c(
            r"(?:cria|crie|criar|comeca|comece|comecar|inicia|inicie|iniciar|novo"
            r"|create|start|make|new|crea|cree|crear|empieza|nuevo|creer|commence"
            r"|demarre|nouveau) "
            r"(?:o |um |uma |a |an |the |el |un |le |une )?"
            r"(?:novo |new |nuevo |nouveau )?" + _P + r" "
            r"(?:chamado |com o nome |de nome |called |named |llamado |appele |nomme )?"
            r"(?P<nome>.+?)"
            r"(?: (?:na|dentro da|em|in|in the|en la|dans le) "
            r"(?:pasta|folder|carpeta|dossier) (?P<pasta>.+))?"
        ),
    ),
    # Ver (estado)
    (
        VER,
        _c(
            r"(?:como (?:esta|ta|anda|vai)|status do|situacao do|resumo do|andamento do"
            r"|me (?:fala|conta|fale|conte) (?:do|sobre o)) "
            r"(?:o )?projeto (?P<nome>.+)"
        ),
    ),
    (
        VER,
        _c(
            r"como (?:esta|ta|anda|vai) (?:o )?(?:meu|esse|este|nosso) projeto(?: atual)?"
            r"|como (?:esta|ta|anda|vai) o projeto atual"
        ),
    ),
    (
        VER,
        _c(
            r"(?:how is|how s|hows|how are things with) (?:the )?project (?P<nome>.+?)"
            r"(?: going| doing| coming along)?"
            r"|(?:what is|what s|whats) the status of (?:the )?project (?P<nome2>.+)"
            r"|status of (?:the )?project (?P<nome3>.+)"
        ),
    ),
    (VER, _c(r"how is my (?:current )?project(?: going| doing)?")),
    (
        VER,
        _c(
            r"(?:como va|como esta|como anda|estado del|resumen del) (?:el )?proyecto"
            r" (?P<nome>.+)"
        ),
    ),
    (
        VER,
        _c(
            r"(?:ou en est|comment va|comment avance|etat du|resume du) (?:le )?projet"
            r" (?P<nome>.+)"
        ),
    ),
    # Falta
    (
        FALTA,
        _c(
            r"(?:o que|oq|que) (?:ainda )?(?:falta|resta) (?:fazer )?"
            r"(?:no|do|pro|para o|em) (?:meu )?projeto(?: (?P<nome>.+))?"
            r"|(?:quais (?:sao )?)?(?:as )?pendencias do projeto (?P<nome2>.+)"
        ),
    ),
    (
        FALTA,
        _c(
            r"what (?:is|s) (?:still )?(?:left|pending|missing)(?: to do)? "
            r"(?:in|on|for) (?:the |my )?project(?: (?P<nome>.+))?"
            r"|whats (?:still )?(?:left|pending|missing)(?: to do)? (?:in|on|for) "
            r"(?:the |my )?project(?: (?P<nome2>.+))?"
            r"|(?:open )?tasks (?:in|of|for) (?:the )?project (?P<nome3>.+)"
        ),
    ),
    (
        FALTA,
        _c(
            r"(?:que|lo que) (?:me )?(?:falta|queda) (?:por hacer |hacer )?"
            r"(?:en|del) (?:el |mi )?proyecto(?: (?P<nome>.+))?"
            r"|(?:los )?pendientes del proyecto (?P<nome2>.+)"
        ),
    ),
    (
        FALTA,
        _c(
            r"(?:qu est-ce qui reste|que reste-t-il|qu est-ce qu il reste)(?: a faire)? "
            r"(?:dans|sur|pour|au) (?:le |mon )?projet(?: (?P<nome>.+))?"
        ),
    ),
    # Decisão ("... que ...")
    (
        DECISAO,
        _c(
            r"(?:anota|anote|anotar|registra|registre|registrar|grava|grave|salva"
            r"|salve|coloca|coloque)(?: (?:a |uma )?decisao)? (?:no|ao|pro|para o|do|em)"
            r" projeto (?P<nome>.+?) que (?P<texto>.+)"
        ),
    ),
    (
        DECISAO,
        _c(
            r"(?:no|do) projeto (?P<nome>.+?) (?:a gente |nos )?"
            r"(?P<texto>(?:decidimos|decidi|ficou decidido) .+)"
        ),
    ),
    (
        DECISAO,
        _c(
            r"(?:note|write down|record|log)(?: (?:a |the )?decision)? (?:in|on|to|for)"
            r" (?:the )?project (?P<nome>.+?) that (?P<texto>.+)"
            r"|(?:in|on|for) (?:the )?project (?P<nome2>.+?) (?P<texto2>we decided .+)"
        ),
    ),
    (
        DECISAO,
        _c(
            r"(?:anota|apunta|registra|guarda)(?: la decision)? en el proyecto"
            r" (?P<nome>.+?) que (?P<texto>.+)"
        ),
    ),
    (
        DECISAO,
        _c(
            r"(?:note|notes|enregistre)(?: la decision)? (?:dans|sur) le projet"
            r" (?P<nome>.+?) que (?P<texto>.+)"
        ),
    ),
    # Pendência (texto antes do projeto)
    (
        PENDENCIA,
        _c(
            r"(?:adiciona|adicione|adicionar|coloca|coloque|cria|crie|anota|anote|inclui"
            r"|inclua|bota|poe)(?: (?:uma|a))? (?:pendencia|tarefa) (?P<texto>.+?) "
            r"(?:no|ao|pro|para o|do|em) projeto (?P<nome>.+)"
            r"|(?:add|create|put)(?: a| an| the)? (?:task|todo|to do|pending item) "
            r"(?P<texto2>.+?) (?:to|in|on|for) (?:the )?project (?P<nome2>.+)"
            r"|(?:anade|agrega|anadir|agregar|crea|pon)(?: una| la)? (?:tarea|pendiente) "
            r"(?P<texto3>.+?) (?:al|en el|para el) proyecto (?P<nome3>.+)"
            r"|(?:ajoute|ajouter|cree|mets)(?: une| la)? tache (?P<texto4>.+?) "
            r"(?:au|dans le|pour le) projet (?P<nome4>.+)"
        ),
    ),
    # Pendência ("... no projeto Lumen comprar domínio": nome e texto grudados)
    (
        PENDENCIA,
        _c(
            r"(?:adiciona|adicione|adicionar|coloca|coloque|cria|crie|anota|anote|inclui"
            r"|inclua|bota|poe)(?: (?:uma|a))? (?:pendencia|tarefa) "
            r"(?:no|ao|pro|para o|em) projeto (?P<junto>.+)"
            r"|(?:add|create|put)(?: a| an)? (?:task|todo|to do) (?:to|in|on|for) "
            r"(?:the )?project (?P<junto2>.+)"
        ),
    ),
    # Concluir
    (
        CONCLUIR,
        _c(
            r"(?:conclui|conclua|concluir|marca|marque|finaliza|finalize|termina|termine"
            r"|fecha|feche|completa|complete|risca|risque|da baixa (?:na|em))"
            r"(?: a)? (?:pendencia|tarefa) (?P<texto>.+?)"
            r"(?: como (?:feita|concluida|pronta|resolvida))?"
            r"(?: (?:do|no|da) projeto (?P<nome>.+))?"
        ),
    ),
    (
        CONCLUIR,
        _c(
            r"(?:complete|finish|close|mark|tick off|check off|done with)(?: the)?"
            r" (?:task|todo|to do) (?P<texto>.+?)"
            r"(?: as (?:done|complete|completed|finished))?"
            r"(?: (?:in|on|of|from|for) (?:the )?project (?P<nome>.+))?"
        ),
    ),
    (
        CONCLUIR,
        _c(
            r"(?:completa|termina|cierra|marca)(?: la| el)? (?:tarea|pendiente)"
            r" (?P<texto>.+?)(?: como (?:hecha|hecho|terminada|terminado|completada))?"
            r"(?: (?:del|en el) proyecto (?P<nome>.+))?"
        ),
    ),
    (
        CONCLUIR,
        _c(
            r"(?:termine|finis|ferme|marque|coche)(?: la)? tache (?P<texto>.+?)"
            r"(?: comme (?:faite|terminee))?(?: (?:du|dans le) projet (?P<nome>.+))?"
        ),
    ),
    # Estado ("... para ...")
    (
        ESTADO,
        _c(
            r"(?:atualiza|atualize|muda|mude|define|defina) o (?:estado|status) do"
            r" projeto (?P<nome>.+?) (?:para|pra) (?P<texto>.+)"
            r"|(?:update|set|change) (?:the )?(?:status|state) of (?:the )?project"
            r" (?P<nome2>.+?) to (?P<texto2>.+)"
            r"|(?:actualiza|cambia) el estado del proyecto (?P<nome3>.+?) a (?P<texto3>.+)"
            r"|(?:mets a jour|change) l etat du projet (?P<nome4>.+?) (?:en|a) (?P<texto4>.+)"
        ),
    ),
    # Arquivar
    (
        ARQUIVAR,
        _c(
            r"(?:arquiva|arquive|arquivar|archive|archiva|archivar) "
            r"(?:o |the |el |le )?(?:projeto|project|proyecto|projet) (?P<nome>.+)"
        ),
    ),
    # Renomear
    (
        RENOMEAR,
        _c(
            r"(?:renomeia|renomeie|renomear|muda o nome do|mude o nome do|troca o nome do)"
            r" (?:o )?projeto (?P<nome>.+?) (?:para|pra) (?P<novo>.+)"
            r"|rename (?:the )?project (?P<nome2>.+?) to (?P<novo2>.+)"
            r"|(?:renombra|cambia el nombre del) (?:el )?proyecto (?P<nome3>.+?) a"
            r" (?P<novo3>.+)"
            r"|renomme (?:le )?projet (?P<nome4>.+?) en (?P<novo4>.+)"
        ),
    ),
    # Continuar
    (
        CONTINUAR,
        _c(
            r"(?:continu[ae]r?|vamos continuar|bora continuar|retoma|retomar|retome"
            r"|voltar|volta|vamos voltar) "
            r"(?:de |a partir de |da |do )?(?:onde|da onde|do ponto (?:onde|em que|que))"
            r" (?:eu )?(?:parei|paramos|tinha parado|estava|tava)"
            r"(?: (?:no|do|com o) projeto (?P<nome>.+))?"
        ),
    ),
    (
        CONTINUAR,
        _c(
            r"(?:o que|oq|que) (?:e que )?(?:eu )?(?:estava|tava) fazendo"
            r"|(?:em que|no que) (?:eu )?(?:estava|tava) trabalhando"
            r"|onde (?:e que )?(?:eu )?parei(?: (?:no|do) projeto (?P<nome>.+))?"
        ),
    ),
    (
        CONTINUAR,
        _c(
            r"(?:continu[ae]r?|retoma|retomar|retome|vamos continuar|bora continuar)"
            r" (?:o )?projeto (?P<nome>.+)"
        ),
    ),
    (
        CONTINUAR,
        _c(
            r"(?:pick up|continue|carry on|resume|let s continue|lets continue)"
            r"(?: from)? where (?:i|we) left off"
            r"(?: (?:on|in|with) (?:the )?project (?P<nome>.+))?"
            r"|what was i (?:doing|working on)"
            r"|where (?:did i|was i|i) (?:leave|left) off"
            r"(?: (?:on|in|with) (?:the )?project (?P<nome2>.+))?"
            r"|(?:continue|resume) (?:the )?project (?P<nome3>.+)"
        ),
    ),
    (
        CONTINUAR,
        _c(
            r"(?:continua|continuar|continue|sigue|seguir|retoma|retomar|sigamos"
            r"|continuemos) (?:desde )?donde lo (?:deje|dejamos|habia dejado)"
            r"(?: (?:en el|del|con el) proyecto (?P<nome>.+))?"
            r"|que estaba haciendo|en que estaba trabajando"
            r"|donde lo (?:deje|dejamos)(?: (?:en el|del) proyecto (?P<nome2>.+))?"
            r"|(?:continua|retoma) el proyecto (?P<nome3>.+)"
        ),
    ),
    (
        CONTINUAR,
        _c(
            r"(?:reprends|reprenons|reprendre|continue|continuons) "
            r"(?:la )?ou (?:je|j|on|nous) "
            r"(?:m etais arrete|m etais arretee|en etais|s etait arrete|en etions"
            r"|nous etions arretes)"
            r"(?: (?:dans|sur|avec) le projet (?P<nome>.+))?"
            r"|qu est-ce que je faisais|sur quoi je travaillais"
            r"|ou j en etais(?: (?:dans|sur) le projet (?P<nome2>.+))?"
            r"|(?:reprends|continue) le projet (?P<nome3>.+)"
        ),
    ),
]

# Só na primeira mensagem (ou por voz): no meio da conversa, é a conversa.
_SO_NO_COMECO = _c(
    r"(?:vamos|bora) continuar|continuando|vamos la|vamos retomar"
    r"|let s continue|lets continue|let us continue|keep going"
    r"|sigamos|continuemos|vamos a continuar|continuons|on continue"
)

# Página Projetos em chinês, hindi e árabe: "<frase>: <projeto>".
_CONTINUAR_OUTROS = tuple(
    normalize(frase)
    for frase in (
        "从上次停下的地方继续",
        "继续上次的工作",
        "जहाँ छोड़ा था वहीं से जारी रखें",
        "जहां छोड़ा था वहीं से जारी रखें",
        "أكمل من حيث توقفت",
        "تابع من حيث توقفت",
    )
)

# --- Cabeça antes de dois-pontos ("decisão no projeto X: texto") ------------
_CABECAS: list[tuple[str, re.Pattern[str]]] = [
    (
        DECISAO,
        _c(
            r"(?:(?:anota|anote|registra|registre|grava|salva|nova|adiciona|adicione)"
            r"(?: (?:a |uma )?decisao)?|decisao) "
            + _EM
            + r" (?:o )?projeto (?P<nome>.+)"
            r"|(?:(?:note|record|log|add)(?: (?:a |the )?decision)?|decision) "
            r"(?:in|on|to|for) (?:the )?project (?P<nome2>.+)"
            r"|(?:(?:anota|apunta|registra)(?: (?:la |una )?decision)?|decision) "
            r"(?:en el|al|para el) proyecto (?P<nome3>.+)"
            r"|(?:(?:note|enregistre|ajoute)(?: (?:la |une )?decision)?|decision) "
            r"(?:dans le|au|pour le|sur le) projet (?P<nome4>.+)"
        ),
    ),
    (
        PENDENCIA,
        _c(
            r"(?:(?:adiciona|adicione|adicionar|coloca|coloque|cria|crie|anota|anote"
            r"|inclui|inclua|bota|poe|nova)(?: (?:uma|a))? )?(?:pendencia|tarefa) "
            + _EM
            + r" (?:o )?projeto (?P<nome>.+)"
            r"|(?:(?:add|create|put|new)(?: a| an)? )?(?:task|todo|to do|pending item) "
            r"(?:to|in|on|for) (?:the )?project (?P<nome2>.+)"
            r"|(?:(?:anade|agrega|crea|pon|nueva)(?: una)? )?(?:tarea|pendiente) "
            r"(?:al|en el|para el) proyecto (?P<nome3>.+)"
            r"|(?:(?:ajoute|cree|mets|nouvelle)(?: une)? )?tache "
            r"(?:au|dans le|pour le) projet (?P<nome4>.+)"
        ),
    ),
    (
        ESTADO,
        _c(
            r"(?:(?:atualiza|atualize|muda|mude|define|defina) )?o (?:estado|status) do"
            r" projeto (?P<nome>.+)"
            r"|(?:(?:update|set|change) )?(?:the )?(?:status|state) of (?:the )?project"
            r" (?P<nome2>.+)"
            r"|(?:(?:actualiza|cambia) )?el estado del proyecto (?P<nome3>.+)"
            r"|(?:(?:mets a jour|change) )?l etat du projet (?P<nome4>.+)"
        ),
    ),
    (
        CONCLUIR,
        _c(
            r"(?:conclui|conclua|concluir|marca como feita|finaliza|termina|completa)"
            r"(?: a)? (?:pendencia|tarefa) (?:do|no|da) projeto (?P<nome>.+)"
            r"|(?:complete|finish|close|mark done)(?: the)? (?:task|todo) "
            r"(?:in|on|of|from) (?:the )?project (?P<nome2>.+)"
        ),
    ),
]

# "Decidimos usar Postgres" -> "usar Postgres".
_PREFIXO_DECISAO = re.compile(
    r"^(?:(?:n[oó]s|a gente)\s+)?(?:decidimos|decidi|ficou decidido|we decided|"
    r"i decided|hemos decidido|decid[ií]|on a d[ée]cid[ée]|nous avons d[ée]cid[ée]|"
    r"j'ai d[ée]cid[ée])\s+(?:que\s+|that\s+|to\s+|de\s+|d')?",
    re.IGNORECASE,
)

# Nomes que querem dizer "o projeto atual".
_ATUAL = frozenset(
    {
        "atual", "meu", "esse", "este", "nosso", "current", "this", "my",
        "actual", "mi", "ce", "mon", "projeto atual", "current project",
    }
)  # fmt: skip

# Dois-pontos de verdade (não de horário "15:30" nem de unidade "C:\").
_DOIS_PONTOS = re.compile(r"(?<!\d):(?!\d)(?![\\/])")


def _grupo(m: re.Match[str], base: str) -> Optional[str]:
    for nome, valor in m.groupdict().items():
        if valor is not None and re.fullmatch(rf"{base}\d*", nome):
            return nome
    return None


def _trecho(texto: str, where: list[int], m: re.Match[str], base: str) -> str:
    grupo = _grupo(m, base)
    if grupo is None:
        return ""
    return original_text(texto, where, m.start(grupo), m.end(grupo))


_PASTA_ORIGINAL = re.compile(
    r"\b(?:pasta|folder|carpeta|dossier)\s+(?P<caminho>(?:[A-Za-z]:[\\/]|[\\/~.]).+)$",
    re.IGNORECASE,
)


def _pasta_original(texto: str) -> str:
    """Caminho como o usuário escreveu: a normalização perde o "/" inicial."""
    m = _PASTA_ORIGINAL.search(texto.strip())
    if m is None:
        return ""
    return m.group("caminho").strip().strip("\"'“”").rstrip(".!?)")


def _nome(bruto: str) -> str:
    nome = bruto.strip(" \"'“”«»")
    if normalize(nome) in _ATUAL:
        return ""
    return nome


def limpar_decisao(texto: str) -> str:
    texto = texto.strip()
    sem = _PREFIXO_DECISAO.sub("", texto).strip()
    return (sem[:1].upper() + sem[1:]) if sem else texto


def _com_dois_pontos(texto: str) -> Optional[Pedido]:
    m = _DOIS_PONTOS.search(texto)
    if m is None:
        return None
    cabeca, cauda = texto[: m.start()], texto[m.end() :].strip()
    if not cauda:
        return None
    t, where = clean_with_map(cabeca)
    for tipo, padrao in _CABECAS:
        achado = padrao.fullmatch(t)
        if achado is None:
            continue
        nome = _nome(_trecho(cabeca, where, achado, "nome"))
        if tipo == DECISAO:
            cauda = limpar_decisao(cauda)
        return Pedido(tipo, nome=nome, texto=cauda)
    return None


def detectar(texto: str, *, primeira: bool = True) -> Optional[Pedido]:
    """O pedido de projeto em *texto*, ou None se não for um."""
    texto = (texto or "").strip()
    if not texto or len(texto) > MAX_CARACTERES:
        return None
    pedido = _com_dois_pontos(texto)
    if pedido is not None:
        return pedido
    t, where = clean_with_map(texto)
    if not t:
        return None
    for tipo, padrao in _FRASES:
        m = padrao.fullmatch(t)
        if m is None:
            continue
        nome = _nome(_trecho(texto, where, m, "nome"))
        if tipo == CRIAR:
            if not nome:
                continue
            pasta = _trecho(texto, where, m, "pasta")
            return Pedido(CRIAR, nome=nome, pasta=_pasta_original(texto) or pasta)
        if tipo == RENOMEAR:
            return Pedido(
                RENOMEAR, nome=nome, novo_nome=_nome(_trecho(texto, where, m, "novo"))
            )
        if tipo == PENDENCIA and _grupo(m, "junto"):
            return Pedido(PENDENCIA, nome=_trecho(texto, where, m, "junto"), junto=True)
        corpo = _trecho(texto, where, m, "texto")
        if tipo == DECISAO:
            corpo = limpar_decisao(corpo)
        return Pedido(tipo, nome=nome, texto=corpo)
    if primeira and _SO_NO_COMECO.fullmatch(t):
        return Pedido(CONTINUAR)
    for frase in _CONTINUAR_OUTROS:
        if frase and t.startswith(frase):
            resto = t[len(frase) :].strip(" -")
            nome = (
                original_text(texto, where, len(t) - len(resto), len(t))
                if resto
                else ""
            )
            return Pedido(CONTINUAR, nome=_nome(nome))
    return None


def menciona_projeto(texto: str) -> bool:
    """A mensagem fala de projeto? (para marcar atividade e pelo roteamento)."""
    return bool(
        re.search(
            r"\b(?:projetos?|projects?|proyectos?|projets?)\b", normalize(texto or "")
        )
    )


__all__ = [
    "ARQUIVAR",
    "CONCLUIR",
    "CONTINUAR",
    "CRIAR",
    "DECISAO",
    "ESTADO",
    "FALTA",
    "LISTAR",
    "PENDENCIA",
    "RENOMEAR",
    "VER",
    "Pedido",
    "detectar",
    "limpar_decisao",
    "menciona_projeto",
]
