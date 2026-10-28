"""Padrões das rotinas: lembretes, anotações, estado do PC, pastas, print,
fechar apps e energia (com confirmação).

``parse`` recebe o texto original e o texto limpo (com o mapa de posições de
``intencoes.clean_with_map``), para devolver lembretes e notas com acento.
"""

from __future__ import annotations

import re
from typing import Optional

from nicx.acoes import confirmacao
from nicx.acoes.intencoes import Action, original_text
from nicx.acoes.tempo import parse_clock, parse_duration, parse_when

# ---------------------------------------------------------------------------
# Pastas e apps que dá para fechar
# ---------------------------------------------------------------------------

# chave -> (como falar, subpastas candidatas dentro do perfil do usuário)
FOLDERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "downloads": ("Downloads", ("Downloads",)),
    "documentos": (
        "Documentos",
        ("Documents", "OneDrive/Documentos", "OneDrive/Documents"),
    ),
    "imagens": ("Imagens", ("Pictures", "OneDrive/Imagens", "OneDrive/Pictures")),
    "musicas": ("Músicas", ("Music",)),
    "videos": ("Vídeos", ("Videos",)),
    "area de trabalho": (
        "Área de Trabalho",
        ("Desktop", "OneDrive/Área de Trabalho", "OneDrive/Desktop"),
    ),
}
_FOLDER_ALIASES = {
    "download": "downloads",
    "baixados": "downloads",
    "fotos": "imagens",
    "musica": "musicas",
    "video": "videos",
    "desktop": "area de trabalho",
    "documento": "documentos",
}

# chave -> (como falar, executáveis do processo)
CLOSABLE: dict[str, tuple[str, tuple[str, ...]]] = {
    "chrome": ("o Chrome", ("chrome.exe",)),
    "google chrome": ("o Chrome", ("chrome.exe",)),
    "edge": ("o Edge", ("msedge.exe",)),
    "navegador": ("o navegador", ("msedge.exe", "chrome.exe", "firefox.exe")),
    "firefox": ("o Firefox", ("firefox.exe",)),
    "spotify": ("o Spotify", ("Spotify.exe",)),
    "bloco de notas": ("o Bloco de Notas", ("notepad.exe",)),
    "notepad": ("o Bloco de Notas", ("notepad.exe",)),
    "vs code": ("o VS Code", ("Code.exe",)),
    "vscode": ("o VS Code", ("Code.exe",)),
    "word": ("o Word", ("WINWORD.EXE",)),
    "excel": ("o Excel", ("EXCEL.EXE",)),
    "powerpoint": ("o PowerPoint", ("POWERPNT.EXE",)),
    "outlook": ("o Outlook", ("OUTLOOK.EXE", "olk.exe")),
    "teams": ("o Teams", ("ms-teams.exe", "Teams.exe")),
    "whatsapp": ("o WhatsApp", ("WhatsApp.exe",)),
    "calculadora": ("a Calculadora", ("CalculatorApp.exe",)),
    "paint": ("o Paint", ("mspaint.exe",)),
}

# ---------------------------------------------------------------------------
# Lembretes e timers
# ---------------------------------------------------------------------------

_REMIND = r"(?:me )?(?:lembra|lembre|lembrar|lembrete|avisa|avise|avisar)(?: me)?"
_CONNECTOR = r"(?:de |que |para |pra |do |da )"
# "me lembra disso", "anota uma coisa": falam de algo de antes ou vago, é com o modelo.
_VAGUE = re.compile(
    r"(?:isso|isto|disso|disto|aquilo|daquilo|essa|esse|uma coisa|alguma coisa|algo"
    r"|o que)\b"
)
_WHEN_START = (
    r"(?:em|daqui|dentro de|hoje|amanha|depois de amanha|as|a|para as|pras"
    r"|meio dia|meia noite)\b"
)


def _split_when(words: list[str], *, at_end: bool) -> Optional[tuple[int, object]]:
    """Acha a fatia de palavras que é um "quando" (no fim ou no começo)."""
    n = len(words)
    spans = range(0, n) if at_end else range(n, 0, -1)
    for i in spans:
        piece = " ".join(words[i:]) if at_end else " ".join(words[:i])
        if not re.match(_WHEN_START, piece):
            continue
        when = parse_when(piece)
        if when is not None:
            return i, when
    return None


def _offsets(t: str) -> list[int]:
    """Posição inicial de cada palavra de ``t``."""
    return [m.start() for m in re.finditer(r"\S+", t)]


def _reminder(text: str, t: str, where: list[int]) -> Optional[Action]:
    m = re.match(_REMIND + r" ", t)
    lead_when = None
    if not m:
        # "daqui a 10 minutos me lembra de ..."
        m2 = re.search(r" " + _REMIND + r" ", t)
        if not m2 or not re.match(_WHEN_START, t):
            return None
        lead_when = parse_when(t[: m2.start()])
        if lead_when is None:
            return None
        rest_start = m2.end()
    else:
        rest_start = m.end()

    rest = t[rest_start:]
    words = rest.split()
    starts = [rest_start + o for o in _offsets(rest)]
    if not words:
        return None

    if lead_when is not None:
        what_start, what_end, when = rest_start, len(t), lead_when
    else:
        found = _split_when(words, at_end=True)
        if found is not None and found[0] > 0:
            i, when = found
            what_start, what_end = rest_start, starts[i] - 1
        else:
            found = _split_when(words, at_end=False)
            if found is None or found[0] >= len(words):
                return None
            i, when = found
            # Horário na frente precisa de conector: "às 3 de ligar" sim,
            # "as 3 leis de Newton" não (é uma pergunta para o modelo).
            if not re.match(_CONNECTOR, t[starts[i] :]):
                return None
            what_start, what_end = starts[i], len(t)

    what_clean = t[what_start:what_end]
    cm = re.match(_CONNECTOR, what_clean)
    if cm:
        what_start += cm.end()
    if _VAGUE.match(t[what_start:what_end]):
        return None
    what = original_text(text, where, what_start, what_end)
    if not what:
        return None
    return Action("remind", target=what, when=when)  # type: ignore[arg-type]


def _timer(t: str) -> Optional[Action]:
    m = re.fullmatch(
        r"(?:(?:coloca|poe|liga|cria|faz|inicia|comeca|marca|bota) )?(?:um )?"
        r"(?:timer|temporizador|cronometro)(?: de| para| por| pra)? (?P<d>.+)",
        t,
    )
    if m:
        duration = parse_duration(m.group("d"))
        if duration is None:
            return None
        from datetime import datetime

        return Action("remind", target="o tempo acabou", when=datetime.now() + duration)
    m = re.fullmatch(
        r"(?:(?:coloca|poe|cria|define|bota|marca) )?(?:um )?(?:alarme|despertador)"
        r"(?: para| pra| pras)? (?P<w>.+)",
        t,
    )
    if m:
        when = parse_clock(m.group("w"), morning=True) or parse_when(m.group("w"))
        if when is None:
            return None
        return Action("remind", target="alarme", when=when)
    return None


def _reminder_admin(t: str) -> Optional[Action]:
    if re.fullmatch(
        r"(?:quais|que) (?:sao )?(?:os )?(?:meus )?(?:lembretes|alarmes|timers)"
        r"(?: que eu tenho)?|(?:lista|mostra|le|leia|fala)(?: os| meus)? "
        r"(?:lembretes|alarmes)|tenho (?:algum )?(?:lembrete|alarme)s?",
        t,
    ):
        return Action("remind_list")
    m = re.fullmatch(
        r"(?:cancela|cancele|apaga|apague|remove|limpa|tira)(?P<all> todos)?"
        r" (?:os |meus |o |meu )?(?P<noun>lembretes?|alarmes?|timers?)",
        t,
    )
    if m:
        noun = m.group("noun")
        kind = {"lembrete": "", "alarme": "alarme", "timer": "timer"}[noun.rstrip("s")]
        if m.group("all") or noun.endswith("s"):
            return Action("remind_clear", target=kind)
        # "cancela o timer": só o próximo timer, não a lista inteira.
        return Action("remind_cancel", target=kind)
    return None


# ---------------------------------------------------------------------------
# Anotações
# ---------------------------------------------------------------------------


def _note(text: str, t: str, where: list[int]) -> Optional[Action]:
    # Só a forma de comando: "você pode anotar ...?" e "anotar à mão ajuda?"
    # são conversa e vão para o modelo.
    if text.rstrip().endswith("?"):
        return None
    m = re.match(
        r"(?:anota|anote|toma nota|tome nota|registra|registre|"
        r"salva uma nota|cria uma nota|faz uma nota)"
        r"(?: (?:ai|pra mim|para mim))?(?: (?:que|de que|uma nota))?\s",
        t,
    )
    # "anota isso ...", "anota uma coisa": vago ou de antes, é com o modelo.
    if not m or _VAGUE.match(t[m.end() :]):
        return None
    what = original_text(text, where, m.end(), len(t))
    return Action("note_add", target=what) if what else None


def _notes_admin(t: str) -> Optional[Action]:
    if re.fullmatch(
        r"(?:le|leia|mostra|lista|fala|quais sao|quais)(?: as| minhas)? "
        r"(?:anotacoes|notas)|o que eu anotei|minhas (?:anotacoes|notas)",
        t,
    ):
        return Action("notes_list")
    if re.fullmatch(
        r"(?:apaga|apague|limpa|limpe)(?: todas)?(?: as| minhas)? (?:anotacoes|notas)",
        t,
    ):
        return Action("notes_clear")
    return None


# ---------------------------------------------------------------------------
# PC: estado, pastas, print, fechar, energia
# ---------------------------------------------------------------------------


def _status(t: str) -> Optional[Action]:
    if re.fullmatch(
        r"como (?:esta|ta) (?:o |meu )?(?:computador|pc|notebook|sistema)"
        r"|(?:status|estado) do (?:pc|computador|sistema|notebook)"
        r"|(?:uso|consumo) de (?:cpu|memoria|ram|processador|disco)"
        r"|quanto de (?:memoria|ram|disco)(?: livre| eu tenho| tem| sobrando)?"
        r"|(?:o )?(?:pc|computador) (?:esta|ta) lento(?: por que)?",
        t,
    ):
        return Action("status")
    return None


def _folder(t: str) -> Optional[Action]:
    m = re.fullmatch(
        r"(?:abre|abra|abrir|mostra|mostre)"
        r" (?:a pasta |pasta |os |as |meus |minhas |a |o )?(?:de |dos |das |do |da )?"
        r"(?:meus |minhas )?(?P<f>.+)",
        t,
    )
    if not m:
        return None
    key = m.group("f")
    key = _FOLDER_ALIASES.get(key, key)
    return Action("folder", target=key) if key in FOLDERS else None


def _screenshot(t: str) -> Optional[Action]:
    if re.fullmatch(
        r"(?:tira|tire|faz|faca|bate|tirar)(?: um| uma)? (?:print|printscreen|"
        r"captura de tela|foto da tela|print da tela)"
        r"|(?:printa|captura|capture|printe) a tela|print da tela|printscreen",
        t,
    ):
        return Action("screenshot")
    return None


def _close(t: str) -> Optional[Action]:
    m = re.fullmatch(r"(?:fecha|feche|fechar|encerra|encerre) (?:o |a )?(?P<a>.+)", t)
    if not m:
        return None
    return Action("close", target=m.group("a")) if m.group("a") in CLOSABLE else None


def _power(t: str) -> Optional[Action]:
    pc = r"(?: o| a)? (?:computador|pc|notebook|maquina)"
    if re.fullmatch(r"(?:desliga|desligue|desligar)" + pc, t):
        return Action("power", op="shutdown")
    if re.fullmatch(r"(?:reinicia|reinicie|reiniciar|reinicializa)" + pc, t):
        return Action("power", op="restart")
    if re.fullmatch(
        r"(?:suspende|suspenda|suspender|hiberna|hibernar)" + pc + r"?"
        r"|(?:coloca|poe|bota)" + pc + r" (?:pra|para) dormir"
        r"|modo (?:de )?(?:suspensao|hibernacao)",
        t,
    ):
        return Action("power", op="suspend")
    if re.fullmatch(r"(?:cancela|cancele|aborta) (?:o )?(?:desligamento|reinicio)", t):
        return Action("power", op="abort")
    return None


def _confirmation(t: str) -> Optional[Action]:
    """Só vale com uma ação pendente; fora disso é conversa comum."""
    if confirmacao.pending() is None:
        return None
    if re.fullmatch(
        r"(?:sim|confirmo|confirma|confirmado|pode|pode sim|sim pode|isso|claro|"
        r"pode (?:desligar|reiniciar|suspender|ir))(?: sim)?",
        t,
    ):
        return Action("confirm")
    if re.fullmatch(r"(?:nao|cancela|cancele|deixa|esquece|melhor nao)(?: nao)?", t):
        return Action("deny")
    return None


def parse(text: str, t: str, where: list[int]) -> Optional[Action]:
    for simple in (
        _confirmation,
        _timer,
        _reminder_admin,
        _notes_admin,
        _status,
        _folder,
        _screenshot,
        _close,
        _power,
    ):
        action = simple(t)
        if action is not None:
            return action
    for with_text in (_reminder, _note):
        action = with_text(text, t, where)
        if action is not None:
            return action
    return None
