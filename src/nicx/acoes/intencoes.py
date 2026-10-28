"""Entende comandos diretos em português ("aumenta o volume", "abre o YouTube").

Só reconhece a frase inteira como comando: "aumenta o volume" vira ação,
"como eu aumento o volume do Windows?" não (vai para o modelo responder).
Tudo aqui é texto puro, sem tocar no sistema; quem executa é ``sistema.py``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Action:
    """Uma ação reconhecida. ``kind`` diz o que fazer; o resto são detalhes."""

    # volume, media, open, search, time, date, battery, lock; e de rotinas.py:
    # remind, remind_list, remind_clear, remind_cancel, note_add, notes_list,
    # notes_clear, status, folder, screenshot, close, power, confirm, deny
    kind: str
    op: str = ""  # volume: up/down/set/mute; media: toggle/next/prev; power
    value: Optional[int] = None  # volume: passos (up/down) ou nível 0-100 (set)
    target: str = ""  # open/folder/close: chave; search: termo; remind/note: texto
    site: str = ""  # search: google ou youtube
    when: Optional[datetime] = None  # remind: quando avisar


@dataclass(frozen=True)
class App:
    label: str  # como o Nicx fala: "o Bloco de Notas"
    kind: str  # exe (programa), uri (protocolo do Windows) ou url (site)
    value: str


_APP_LIST: list[tuple[tuple[str, ...], App]] = [
    (("bloco de notas", "notepad"), App("o Bloco de Notas", "exe", "notepad")),
    (("calculadora",), App("a Calculadora", "exe", "calc")),
    (
        ("explorador de arquivos", "explorador", "arquivos", "meus arquivos"),
        App("o Explorador de Arquivos", "exe", "explorer"),
    ),
    (
        ("configuracoes", "configuracao", "ajustes", "configuracoes do windows"),
        App("as Configurações", "uri", "ms-settings:"),
    ),
    (("gerenciador de tarefas",), App("o Gerenciador de Tarefas", "exe", "taskmgr")),
    (("paint",), App("o Paint", "exe", "mspaint")),
    (
        ("terminal", "powershell", "prompt de comando"),
        App("o terminal", "exe", "powershell"),
    ),
    (
        ("vs code", "vscode", "visual studio code", "code"),
        App("o VS Code", "exe", "code"),
    ),
    (("chrome", "google chrome"), App("o Chrome", "exe", "chrome")),
    (("edge", "microsoft edge"), App("o Edge", "uri", "microsoft-edge:")),
    (("navegador", "internet"), App("o navegador", "url", "https://www.google.com")),
    (("word",), App("o Word", "exe", "winword")),
    (("excel",), App("o Excel", "exe", "excel")),
    (("powerpoint",), App("o PowerPoint", "exe", "powerpnt")),
    (("outlook",), App("o Outlook", "exe", "outlook")),
    (("teams",), App("o Teams", "uri", "msteams:")),
    (("spotify",), App("o Spotify", "uri", "spotify:")),
    (("whatsapp",), App("o WhatsApp", "uri", "whatsapp:")),
    (("youtube",), App("o YouTube", "url", "https://www.youtube.com")),
    (("google",), App("o Google", "url", "https://www.google.com")),
    (("gmail", "email", "e-mail"), App("o Gmail", "url", "https://mail.google.com")),
    (("github",), App("o GitHub", "url", "https://github.com")),
    (
        ("lumen", "falkyria lumen"),
        App("o Lumen", "url", "https://falkyria-lumen.vercel.app"),
    ),
    (("netflix",), App("a Netflix", "url", "https://www.netflix.com")),
    (("instagram",), App("o Instagram", "url", "https://www.instagram.com")),
]
APPS: dict[str, App] = {name: app for names, app in _APP_LIST for name in names}

# Passos de tecla de volume (cada um muda ~2% no Windows).
STEP_NORMAL = 5
STEP_SMALL = 3
STEP_BIG = 10


# Horário com dois-pontos ("às 15:30"): os dois-pontos sairiam com a pontuação.
_CLOCK_COLON = re.compile(r"(\d{1,2}):(\d{2})\b")
# Data com barra ("30/10"): a barra também sairia; vira "30-10".
_DATE_SLASH = re.compile(r"(?<=\d)/(?=\d)")


def normalize(text: str) -> str:
    """Minúsculas, sem acento, sem pontuação e com espaços simples."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _CLOCK_COLON.sub(r"\1h\2", text)  # "15:30" -> "15h30"
    text = _DATE_SLASH.sub("-", text)  # "30/10" -> "30-10"
    text = re.sub(r"[^\w\s%-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Gentilezas em volta do comando, que não mudam o que é pedido.
_PREFIX = re.compile(
    r"^(?:(?:ei|oi|ok|ola|e ai)\s+)?(?:nicx|nix|nics|niks)?\s*"
    r"(?:(?:por favor|pfv|pf)\s+)?"
    r"(?:(?:da pra|pode|poderia|consegue|voce pode|voce consegue|quero que voce|"
    r"queria que voce)\s+)?"
)
_SUFFIX = re.compile(
    r"(?:\s+(?:por favor|pfv|pf|pra mim|para mim|ai|agora|ja|rapidinho|nicx))+$"
)


def _clean(text: str) -> str:
    return clean_with_map(text)[0]


def clean_with_map(text: str) -> tuple[str, list[int]]:
    """Como ``_clean``, mais a posição no texto original de cada caractere.

    Serve para devolver trechos com acento e maiúsculas ("ligar pra mãe"),
    já que a comparação é feita sem eles.
    """
    chars: list[str] = []
    where: list[int] = []
    colons = {m.start() + len(m.group(1)) for m in _CLOCK_COLON.finditer(text)}
    slashes = {m.start() for m in _DATE_SLASH.finditer(text)}
    for i, ch in enumerate(text):
        if i in colons or i in slashes:
            chars.append("h" if i in colons else "-")
            where.append(i)
            continue
        base = unicodedata.normalize("NFKD", ch.lower())
        for c in base:
            if unicodedata.combining(c):
                continue
            if re.match(r"[\w%-]", c):
                chars.append(c)
                where.append(i)
            elif chars and chars[-1] != " ":
                chars.append(" ")
                where.append(i)
    t = "".join(chars)
    start, end = 0, len(t)
    while start < end and t[start] == " ":
        start += 1
    while end > start and t[end - 1] == " ":
        end -= 1
    m = _PREFIX.match(t, start, end)
    if m:
        start = m.end()
        while start < end and t[start] == " ":
            start += 1
    m = _SUFFIX.search(t, start, end)
    if m and m.end() == end:
        end = m.start()
    return t[start:end], where[start:end]


def original_text(text: str, where: list[int], start: int, end: int) -> str:
    """O trecho ``[start:end]`` do texto limpo, tirado do texto original."""
    if start >= end:
        return ""
    return text[where[start] : where[end - 1] + 1].strip(" ,.:;!?-")


_NOUN = (
    r"(?:o |a )?(?:volume|som|audio)"
    r"(?: do (?:computador|pc|notebook|windows|sistema))?"
)
# "aumento" e "aumentasse" aparecem de verdade: o Whisper troca "aumenta"
# por "aumento", e "queria que você aumentasse o volume" é um pedido.
_UP = (
    r"(?:aumenta|aumente|aumentar|aumento|aumentasse|sobe|suba|subir|subisse|"
    r"coloca mais|bota mais|mais)"
)
_DOWN = (
    r"(?:abaixa|abaixe|abaixar|abaixasse|diminui|diminua|diminuir|diminuisse|"
    r"baixa|baixe|baixar|baixasse|reduz|reduza|reduzir|reduzisse|menos)"
)
_INTENSITY = {
    "": STEP_NORMAL,
    "um pouco": STEP_SMALL,
    "um pouquinho": STEP_SMALL,
    "so um pouco": STEP_SMALL,
    "bastante": STEP_BIG,
    "muito": STEP_BIG,
    "mais": STEP_NORMAL,
}
_MAX = {"no maximo", "ao maximo", "ate o maximo", "tudo"}
_MIN = {"no minimo", "ao minimo", "ate o minimo", "no zero"}


def _volume(t: str) -> Optional[Action]:
    m = re.fullmatch(rf"(?P<dir>{_UP}|{_DOWN}) {_NOUN}(?: (?P<rest>.+))?", t)
    if m:
        rest = m.group("rest") or ""
        up = re.fullmatch(_UP, m.group("dir")) is not None
        if rest in _MAX and up:
            return Action("volume", "set", 100)
        if rest in _MIN and not up:
            return Action("volume", "set", 0)
        if rest in _INTENSITY:
            return Action("volume", "up" if up else "down", _INTENSITY[rest])
        return None
    m = re.fullmatch(rf"{_NOUN} mais (?P<d>alto|baixo)", t)
    if m:
        return Action("volume", "up" if m.group("d") == "alto" else "down", STEP_NORMAL)
    m = re.fullmatch(
        rf"(?:(?:coloca|bota|deixa|poe|ajusta|muda|define) )?{_NOUN} "
        r"(?:em|para|pra|no|na|a) (?P<n>\d{1,3}|maximo|minimo|zero)"
        r"(?: ?%| por cento)?",
        t,
    )
    if m:
        n = m.group("n")
        level = {"maximo": 100, "minimo": 0, "zero": 0}.get(n)
        if level is None:
            level = int(n)
        if 0 <= level <= 100:
            return Action("volume", "set", level)
        return None
    if re.fullmatch(
        r"(?:muta|mute|mutar|silencia|silencie|silenciar|desmuta|desmute|desmutar|"
        r"tira o som|desliga o som|liga o som|volta o som|sem som)",
        t,
    ):
        return Action("volume", "mute")
    return None


def _media(t: str) -> Optional[Action]:
    noun = r"(?: (?:a |o )?(?:musica|video|midia|som))"
    if re.fullmatch(
        rf"(?:pausa|pause|pausar|despausa|play|da play|continua|continuar|retoma|"
        rf"retomar|toca|tocar){noun}?|(?:para|parar){noun}",
        t,
    ):
        return Action("media", "toggle")
    if re.fullmatch(
        r"(?:proxima|pula|pular|avanca|avancar|passa)"
        r"(?: (?:a |de |essa |esta )?(?:musica|faixa|video))?",
        t,
    ):
        return Action("media", "next")
    if re.fullmatch(
        r"(?:volta|voltar) (?:a |pra |para )?(?:musica|faixa)(?: anterior)?"
        r"|(?:musica|faixa) anterior|anterior",
        t,
    ):
        return Action("media", "prev")
    return None


def _open(t: str) -> Optional[Action]:
    m = re.fullmatch(
        r"(?:abre|abra|abrir|abri|inicia|inicie|iniciar|executa|execute|"
        r"liga|ligar) (?:o |a |os |as )?(?P<t>.+)",
        t,
    )
    if not m:
        return None
    target = re.sub(
        r"^(?:site|app|aplicativo|programa) (?:do |da |de )?", "", m.group("t")
    )
    return Action("open", target=target) if target in APPS else None


def _search(t: str) -> Optional[Action]:
    m = re.fullmatch(
        r"(?:pesquisa|pesquise|pesquisar|procura|procure|procurar|busca|busque|"
        r"buscar) (?:por )?(?P<q>.+?) no (?P<s>google|youtube)",
        t,
    )
    if m:
        return Action("search", target=m.group("q"), site=m.group("s"))
    return None


def _info(t: str) -> Optional[Action]:
    if re.fullmatch(
        r"(?:que|quais) (?:horas? (?:sao|e)|hora e)(?: agora)?"
        r"|(?:me )?(?:diz|diga|fala|fale) (?:as |que )?horas(?: sao)?",
        t,
    ):
        return Action("time")
    if re.fullmatch(
        r"(?:que|qual) (?:dia|data) (?:e )?hoje|hoje e que dia"
        r"|qual (?:e )?a data(?: de hoje)?|que dia e hoje",
        t,
    ):
        return Action("date")
    if re.fullmatch(
        r"(?:quanto (?:de |tem de |esta a |ta a )?bateria(?: tem| eu tenho)?"
        r"|como (?:esta|ta) a bateria|nivel da bateria|bateria)",
        t,
    ):
        return Action("battery")
    if re.fullmatch(
        r"(?:bloqueia|bloquear|bloqueie|trava|travar|trave) "
        r"(?:o |a )?(?:computador|pc|tela|notebook)",
        t,
    ):
        return Action("lock")
    return None


def parse(text: str) -> Optional[Action]:
    """A ação que a frase pede, ou None se não for um comando direto."""
    from nicx.acoes import rotinas

    t, where = clean_with_map(text)
    if not t or len(t) > 200:
        return None
    action = rotinas.parse(text, t, where)
    if action is not None or len(t) > 80:
        return action
    for matcher in (_volume, _media, _open, _search, _info):
        action = matcher(t)
        if action is not None:
            return action
    return None
