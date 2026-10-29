"""Comandos diretos em inglês, espanhol e francês.

O português mora em ``intencoes`` e ``rotinas``; aqui ficam só os pedidos
mais comuns nos outros três idiomas: hora, data, volume, mídia, abrir app ou
site, pesquisar, bateria, bloquear a tela, timer, alarme, lembrete simples,
energia (com confirmação), desfazer a organização de uma pasta e mandar a
agenda para o Google Agenda ou o Outlook ("send it to Google Calendar"). Como no
português, só a frase inteira vira comando; perguntas vão para o modelo.

Chinês, hindi e árabe não são lidos aqui: vão para o modelo, que responde
no idioma e tem a ferramenta ``controle_pc``. A única exceção são as
palavras exatas de confirmar, negar e cancelar o desligamento, que as
próprias respostas pedem (``parse_exato``).

O texto chega limpo por ``intencoes.clean_with_map`` (minúsculas, sem
acento, "15:30" vira "15h30", apóstrofo vira espaço: "what's" -> "what s").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from nicx.acoes import confirmacao
from nicx.acoes.intencoes import (
    APPS,
    STEP_BIG,
    STEP_NORMAL,
    STEP_SMALL,
    Action,
    original_text,
)
from nicx.acoes.tempo import parse_clock

# Textos internos dos lembretes de timer e alarme (os mesmos de ``rotinas``).
_TIMER_TEXT = "o tempo acabou"
_ALARM_TEXT = "alarme"


@dataclass(frozen=True)
class _Lingua:
    """Padrões de um idioma. ``<NUM>`` é trocado pelos números do idioma."""

    prefixo: str
    sufixo: str
    # Informações e tela
    hora: str
    data: str
    bateria: str
    bloquear: str
    # Volume
    vol_nome: str
    vol_sobe: str
    vol_desce: str
    vol_definir: str
    vol_niveis: dict[str, int]
    intensidade: dict[str, int]
    vol_max: frozenset[str]
    vol_min: frozenset[str]
    mudo: str
    # Mídia
    midia_alternar: str
    midia_proxima: str
    midia_anterior: str
    # Abrir e pesquisar
    abrir: str
    abrir_limpa: str
    apps: dict[str, str]
    pesquisar: tuple[str, ...]
    # Energia, confirmação, desfazer organização
    energia: tuple[tuple[str, str], ...]
    confirmar: str
    negar: str
    desfazer: str
    # Timer, alarme e lembrete
    timer: str
    alarme: str
    lembrar: str
    conector: str
    vago: str
    quando_inicio: str
    em: str
    numeros: dict[str, int]
    unidades: dict[str, int]
    e: str
    meia_hora: str
    hora_e_meia: str
    relogio: str
    dias: dict[str, str]
    meio: dict[str, str]
    periodos: dict[str, str]
    # Opcionais
    vol_depois: str = ""  # "turn the volume up"
    vol_frases: tuple[tuple[str, str], ...] = ()  # "louder", "plus fort"
    timer_antes: str = ""  # "set a 10 minute timer"
    minutos_palavra: dict[str, int] = field(default_factory=dict)
    dia_noite: frozenset[str] = frozenset()  # "tonight": sem período, é à noite


_CN = STEP_NORMAL
_CS = STEP_SMALL
_CB = STEP_BIG

# ---------------------------------------------------------------------------
# Inglês
# ---------------------------------------------------------------------------

_EN = _Lingua(
    prefixo=(
        r"(?:(?:hey|hi|hello|ok|okay|yo)\s+)?(?:nicx|nix|nics|niks)?\s*"
        r"(?:please\s+)?"
        r"(?:(?:can you|could you|would you|will you|can u|i want you to|"
        r"i d like you to|i would like you to|go ahead and)\s+)?(?:please\s+)?"
    ),
    sufixo=r"(?:\s+(?:please|for me|now|right now|nicx|thanks|thank you))+$",
    hora=(
        r"what time is it|what s the time|whats the time|what is the time"
        r"|(?:tell|give) me the time|(?:the )?current time"
        r"|do you (?:know|have) the time"
    ),
    data=(
        r"what(?: s| is)? (?:the )?date(?: today| is it(?: today)?)?"
        r"|whats (?:the )?date(?: today)?|what(?: s| is)? today s date"
        r"|whats today s date|what day is (?:it|today)(?: today)?"
        r"|what is the day today|(?:tell me )?today s date"
        r"|what day of the week is it(?: today)?"
    ),
    bateria=(
        r"(?:(?:how much|what s|what is|whats|check)(?: the| my)? )?battery"
        r"(?: level| life| percentage| status| left)?"
        r"(?: do i have(?: left)?| is left| left)?"
        r"|how(?: s| is) (?:the |my )?battery(?: doing)?"
    ),
    bloquear=r"lock (?:the |my )?(?:computer|pc|screen|laptop|notebook|workstation)",
    vol_nome=r"(?:the )?(?:volume|sound|audio)",
    vol_sobe=r"(?:turn up|crank up|pump up|raise|increase|boost)",
    vol_desce=r"(?:turn down|lower|decrease|reduce)",
    vol_depois=(
        r"(?:turn |crank |set )?(?:the )?(?:volume|sound|audio)"
        r" (?:(?P<sobe>up)|(?P<desce>down))(?: (?P<rest>.+))?"
    ),
    vol_frases=(
        (r"(?:make it |a bit |a little |a little bit )?louder", "up"),
        (r"(?:make it |a bit |a little |a little bit )?(?:quieter|softer)", "down"),
    ),
    vol_definir=(
        r"(?:(?:set|put|turn|change|make) )?(?:the )?(?:volume|sound)"
        r" (?:to|at) (?P<n>\d{1,3}|max|maximum|zero|minimum)(?: ?%| percent)?"
    ),
    vol_niveis={"max": 100, "maximum": 100, "zero": 0, "minimum": 0},
    intensidade={
        "": _CN,
        "a bit": _CS,
        "a little": _CS,
        "a little bit": _CS,
        "slightly": _CS,
        "a lot": _CB,
        "a lot more": _CB,
    },
    vol_max=frozenset(
        {"all the way", "all the way up", "to the max", "to max", "to the maximum"}
    ),
    vol_min=frozenset({"all the way down", "to zero", "to the minimum"}),
    mudo=(
        r"mute|unmute|(?:mute|unmute) (?:the )?(?:sound|audio|volume|computer|pc)"
        r"|(?:turn|switch) (?:the )?sound (?:off|on)"
        r"|(?:turn|switch) (?:off|on) the sound"
    ),
    midia_alternar=(
        r"(?:pause|play|unpause)(?: (?:the |my )?(?:music|song|video|media|track))?"
        r"|(?:resume|continue|stop) (?:the |my )?(?:music|song|video|media|track)"
        r"|resume"
    ),
    midia_proxima=(
        r"(?:next|skip)(?: (?:the |this )?(?:song|track|video))?"
        r"|(?:play the )?next (?:song|track|video)|next one"
    ),
    midia_anterior=(
        r"previous(?: (?:song|track|video))?"
        r"|(?:play the |go back to the |back to the )?(?:previous|last)"
        r" (?:song|track|video)"
    ),
    abrir=r"(?:open|launch|start|run|bring up|fire up) (?:the |my |up )?(?P<t>.+)",
    abrir_limpa=(
        r"^(?:app |application |program |website |site |the )"
        r"|(?: app| application| program| website| site)$"
    ),
    apps={
        "calculator": "calculadora",
        "file explorer": "explorador de arquivos",
        "explorer": "explorador de arquivos",
        "files": "explorador de arquivos",
        "my files": "explorador de arquivos",
        "settings": "configuracoes",
        "windows settings": "configuracoes",
        "task manager": "gerenciador de tarefas",
        "command prompt": "terminal",
        "browser": "navegador",
        "web browser": "navegador",
        "mail": "gmail",
    },
    pesquisar=(
        r"(?:search|look up|google)(?: for)? (?P<q>.+?) on (?P<s>google|youtube)",
        r"(?:search|look) (?P<s>google|youtube) for (?P<q>.+)",
    ),
    energia=(
        (
            r"(?:shut down|shutdown|turn off|power off|switch off)"
            r" (?:the |my )?(?:computer|pc|laptop|machine)",
            "shutdown",
        ),
        (r"(?:restart|reboot) (?:the |my )?(?:computer|pc|laptop|machine)", "restart"),
        (
            r"(?:put|send) (?:the |my )?(?:computer|pc|laptop|machine) to sleep"
            r"|(?:suspend|hibernate)(?: (?:the |my )?(?:computer|pc|laptop|machine))?"
            r"|sleep mode",
            "suspend",
        ),
        (r"(?:cancel|abort|stop) (?:the )?(?:shutdown|restart|reboot)", "abort"),
    ),
    confirmar=(
        r"(?:(?:yes|yeah|yep|sure|ok|okay) )?(?:i )?confirm(?:ed)?"
        r"|yes|yeah|yep|sure|go ahead|do it|yes do it|yes go ahead"
    ),
    negar=(
        r"no|nope|cancel|cancel it|don t|do not|never mind|nevermind|forget it"
        r"|no thanks|no thank you|don t do it"
    ),
    desfazer=r"undo (?:the )?(?:organization|organizing|sorting|cleanup)",
    timer=(
        r"(?:(?:set|start|put on|create|make|run) )?(?:a |an )?(?:timer|countdown)"
        r"(?: for| of)? (?P<d>.+)"
    ),
    timer_antes=r"(?:(?:set|start|create|make|run) )?(?:a |an )?(?P<d>.+?)[ -]timer",
    alarme=(
        r"(?:(?:set|create|put|make) )?(?:an |the |my )?alarm(?: clock)?"
        r"(?: for| at)? (?P<w>.+)|wake me up(?: at)? (?P<w2>.+)"
    ),
    lembrar=r"remind me(?: to| that| about| of)?",
    conector=r"(?:to|that|about|of) ",
    vago=r"(?:this|that|it|something|about it|about this|about that|of that|of it)\b",
    quando_inicio=r"(?:in|within|after|at|today|tomorrow|tonight|noon|midnight)\b",
    em=r"(?:in|within|after)",
    numeros={
        "a": 1,
        "an": 1,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "fifteen": 15,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "forty five": 45,
        "fifty": 50,
        "sixty": 60,
        "ninety": 90,
    },
    unidades={
        "second": 1,
        "seconds": 1,
        "sec": 1,
        "secs": 1,
        "minute": 60,
        "minutes": 60,
        "min": 60,
        "mins": 60,
        "hour": 3600,
        "hours": 3600,
        "hr": 3600,
        "hrs": 3600,
    },
    e=" and ",
    meia_hora=r"(?:a )?half (?:an )?hour",
    hora_e_meia=r"(?P<n><NUM>) and a half hours?|(?P<n2><NUM>) hours? and a half",
    relogio=(
        r"(?:(?P<day>today|tomorrow|tonight) )?(?:at )?"
        r"(?:(?P<noon>noon|midnight)"
        r"|(?P<h><NUM>)(?:h(?P<m>\d{2}))?(?: o ?clock)?"
        r"(?: ?(?P<per>am|pm|a m|p m|in the morning|in the afternoon|in the evening"
        r"|at night|tonight))?)"
        r"(?: (?P<day2>today|tomorrow|tonight))?"
    ),
    dias={"today": "hoje", "tomorrow": "amanha", "tonight": "hoje"},
    meio={"noon": "meio dia", "midnight": "meia noite"},
    periodos={
        "am": " da manha",
        "a m": " da manha",
        "in the morning": " da manha",
        "pm": " da tarde",
        "p m": " da tarde",
        "in the afternoon": " da tarde",
        "in the evening": " da noite",
        "at night": " da noite",
        "tonight": " da noite",
    },
    dia_noite=frozenset({"tonight"}),
)

# ---------------------------------------------------------------------------
# Espanhol
# ---------------------------------------------------------------------------

_ES_PC = r"(?:el |la |mi )?(?:ordenador|computadora|computador|pc|equipo|portatil)"

_ES = _Lingua(
    prefixo=(
        r"(?:(?:hola|oye|ey|ok|vale|eh)\s+)?(?:nicx|nix|nics|niks)?\s*"
        r"(?:por favor\s+)?"
        r"(?:(?:puedes|podrias|me puedes|me podrias|quiero que|necesito que)\s+)?"
        r"(?:por favor\s+)?"
    ),
    sufixo=r"(?:\s+(?:por favor|porfa|porfavor|para mi|ahora|ya|nicx|gracias))+$",
    hora=(
        r"que hora es(?: ahora)?|que horas son"
        r"|(?:me )?(?:dices|dirias|puedes decir) (?:la hora|que hora es)"
        r"|dime (?:la hora|que hora es)|tienes hora|la hora"
    ),
    data=(
        r"que (?:dia|fecha) es hoy|(?:cual|que) es la fecha(?: de hoy)?"
        r"|a que (?:dia|fecha) estamos(?: hoy)?|que dia es|que fecha es"
        r"|dime la fecha(?: de hoy)?|hoy que dia es"
    ),
    bateria=(
        r"(?:cuanta |cuanto de )?bateria(?: me queda| queda| tengo| hay| tiene)?"
        r"|como (?:esta|va) la bateria|nivel de (?:la )?bateria"
    ),
    bloquear=(
        r"(?:bloquea|bloquear|bloquee|bloquees) (?:el |la |mi )?"
        r"(?:ordenador|computadora|computador|pc|pantalla|portatil|equipo)"
    ),
    vol_nome=r"(?:el )?(?:volumen|sonido|audio)",
    vol_sobe=(
        r"(?:sube|subir|suba|subas|subele|subeme|aumenta|aumentar|aumente|aumentes"
        r"|eleva|elevar)"
    ),
    vol_desce=(
        r"(?:baja|bajar|baje|bajes|bajale|bajame|disminuye|disminuir|disminuya"
        r"|reduce|reducir|reduzca)"
    ),
    vol_frases=(
        (
            r"(?:pon(?:lo)? )?(?:el )?(?:volumen|sonido) mas (?:alto|fuerte)"
            r"|mas (?:alto|fuerte) el (?:volumen|sonido)",
            "up",
        ),
        (
            r"(?:pon(?:lo)? )?(?:el )?(?:volumen|sonido) mas bajo"
            r"|mas bajo el (?:volumen|sonido)",
            "down",
        ),
    ),
    vol_definir=(
        r"(?:(?:pon|ponme|pone|ajusta|deja|cambia|sube|baja|subeme|bajame) )?"
        r"(?:el )?(?:volumen|sonido) (?:a|al|en) (?P<n>\d{1,3}|maximo|minimo|cero)"
        r"(?: ?%| por ciento)?"
    ),
    vol_niveis={"maximo": 100, "minimo": 0, "cero": 0},
    intensidade={
        "": _CN,
        "un poco": _CS,
        "un poquito": _CS,
        "un poco mas": _CS,
        "mucho": _CB,
        "bastante": _CB,
        "mucho mas": _CB,
    },
    vol_max=frozenset({"al maximo", "a tope", "todo", "a todo"}),
    vol_min=frozenset({"al minimo", "a cero"}),
    mudo=(
        r"silencia|silenciar|silencio|mutea|mutear"
        r"|silencia (?:el )?(?:sonido|audio|volumen|ordenador)|quita el sonido"
        r"|(?:activa|pon|vuelve a poner) el sonido|sin sonido"
    ),
    midia_alternar=(
        r"(?:pausa|pausar|pon pausa|reanuda|reanudar|play|dale play|dale al play"
        r"|reproduce)(?: (?:la |el )?(?:musica|cancion|video))?"
        r"|(?:continua|para|parar|deten|detener) (?:la |el )?(?:musica|cancion|video)"
    ),
    midia_proxima=(
        r"(?:siguiente|salta|saltar)(?: (?:cancion|pista|video))?"
        r"|(?:la )?(?:siguiente|proxima) (?:cancion|pista|video)"
        r"|(?:pasa|pon|salta) (?:a )?(?:la )?(?:siguiente|proxima)"
        r"(?: (?:cancion|pista|video))?"
        r"|(?:pasa|salta) (?:esta |la )?(?:cancion|pista|video)"
    ),
    midia_anterior=(
        r"(?:la )?(?:cancion|pista) anterior"
        r"|(?:vuelve|volver|regresa|pon) (?:a )?la (?:cancion |pista )?anterior"
    ),
    abrir=(
        r"(?:abre|abrir|abra|abreme|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar)"
        r" (?:el |la |los |las |mi )?(?P<t>.+)"
    ),
    abrir_limpa=(
        r"^(?:(?:app|aplicacion|programa|sitio|pagina|web)(?: de| del)? )"
        r"|(?: app| aplicacion| programa| web)$"
    ),
    apps={
        "bloc de notas": "bloco de notas",
        "explorador de archivos": "explorador de arquivos",
        "explorador": "explorador de arquivos",
        "archivos": "explorador de arquivos",
        "mis archivos": "explorador de arquivos",
        "configuracion": "configuracoes",
        "ajustes": "configuracoes",
        "administrador de tareas": "gerenciador de tarefas",
        "simbolo del sistema": "terminal",
        "correo": "gmail",
        "correo electronico": "gmail",
    },
    pesquisar=(
        r"(?:busca|buscar|busque|buscame|investiga)(?: por| sobre)?"
        r" (?P<q>.+?) en (?P<s>google|youtube)",
        r"(?:busca|buscar|busque|buscame) en (?P<s>google|youtube)"
        r"(?: por| sobre)? (?P<q>.+)",
    ),
    energia=(
        (r"(?:apaga|apagar|apague) " + _ES_PC, "shutdown"),
        (r"(?:reinicia|reiniciar|reinicie) " + _ES_PC, "restart"),
        (
            r"(?:suspende|suspender|suspenda|hiberna|hibernar)(?: " + _ES_PC + r")?"
            r"|pon " + _ES_PC + r" a dormir|modo (?:de )?suspension",
            "suspend",
        ),
        (r"(?:cancela|cancelar|cancele|aborta) (?:el )?(?:apagado|reinicio)", "abort"),
    ),
    confirmar=(
        r"si|si confirmo|confirmo|confirmado|confirma|lo confirmo|adelante|hazlo"
        r"|si hazlo|claro|si claro|dale"
    ),
    negar=r"no|cancela|cancelar|olvidalo|dejalo|mejor no|no gracias|no lo hagas",
    desfazer=r"(?:deshaz|deshacer|deshaga) (?:la )?(?:organizacion|ordenacion)",
    timer=(
        r"(?:(?:pon|ponme|pone|crea|inicia|programa|activa) )?(?:un )?"
        r"(?:temporizador|timer|cronometro)(?: de| para| por)? (?P<d>.+)"
    ),
    alarme=(
        r"(?:(?:pon|ponme|crea|programa|activa) )?(?:una |un )?(?:alarma|despertador)"
        r"(?: para| a)? (?P<w>.+)|despiertame(?: a)? (?P<w2>.+)"
    ),
    lembrar=(
        r"(?:recuerdame|recordame|recuerdeme|acuerdame|hazme acordar|avisame"
        r"|recordarme)(?: de| que| para)?"
    ),
    conector=r"(?:de|que|para) ",
    vago=r"(?:esto|eso|aquello|algo|lo que|de eso|de esto)\b",
    quando_inicio=(
        r"(?:en|dentro de|a las|a la|hoy|manana|pasado manana|al mediodia"
        r"|a medianoche|mediodia|medianoche)\b"
    ),
    em=r"(?:en|dentro de)",
    numeros={
        "un": 1,
        "una": 1,
        "uno": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
        "once": 11,
        "doce": 12,
        "quince": 15,
        "veinte": 20,
        "treinta": 30,
        "cuarenta": 40,
        "cuarenta y cinco": 45,
        "cincuenta": 50,
        "sesenta": 60,
        "noventa": 90,
    },
    unidades={
        "segundo": 1,
        "segundos": 1,
        "seg": 1,
        "minuto": 60,
        "minutos": 60,
        "min": 60,
        "hora": 3600,
        "horas": 3600,
        "h": 3600,
    },
    e=" y ",
    meia_hora=r"media hora",
    hora_e_meia=r"(?P<n><NUM>) horas? y media",
    relogio=(
        r"(?:(?P<day>hoy|manana|pasado manana) )?"
        r"(?:(?:a las|a la|para las|para la|las|la) )?"
        r"(?:(?P<noon>al mediodia|mediodia|a medianoche|medianoche)"
        r"|(?P<h><NUM>)(?:h(?P<m>\d{2})| y (?P<mw>media|cuarto|\d{1,2}))?"
        r"(?: ?(?:h|horas?))?"
        r"(?: (?P<per>de la manana|de la tarde|de la noche|de la madrugada))?)"
        r"(?: (?P<day2>de hoy|de manana|hoy|manana))?"
    ),
    dias={
        "hoy": "hoje",
        "manana": "amanha",
        "pasado manana": "depois de amanha",
        "de hoy": "hoje",
        "de manana": "amanha",
    },
    meio={
        "al mediodia": "meio dia",
        "mediodia": "meio dia",
        "a medianoche": "meia noite",
        "medianoche": "meia noite",
    },
    periodos={
        "de la manana": " da manha",
        "de la tarde": " da tarde",
        "de la noche": " da noite",
        "de la madrugada": " da madrugada",
    },
    minutos_palavra={"media": 30, "cuarto": 15},
)

# ---------------------------------------------------------------------------
# Francês
# ---------------------------------------------------------------------------

_FR_PC = r"(?:l |le |mon |ma )?(?:ordinateur|ordi|pc|portable|machine)"

_FR = _Lingua(
    prefixo=(
        r"(?:(?:salut|hey|he|ok|dis|bonjour)\s+)?(?:nicx|nix|nics|niks)?\s*"
        r"(?:(?:s il te plait|s il vous plait|stp|svp)\s+)?"
        r"(?:(?:peux[ -]tu|pourrais[ -]tu|pouvez[ -]vous|pourriez[ -]vous|tu peux"
        r"|tu pourrais|est[ -]ce que tu peux|je veux que tu|j aimerais que tu)\s+)?"
    ),
    sufixo=(
        r"(?:\s+(?:s il te plait|s il vous plait|stp|svp|pour moi|maintenant|merci"
        r"|nicx))+$"
    ),
    hora=(
        r"quelle heure est[ -]il(?: maintenant)?|il est quelle heure"
        r"|quelle heure il est|(?:tu as|vous avez|t as) l heure"
        r"|(?:donne|dis)[ -]moi l heure"
    ),
    data=(
        r"quel jour (?:sommes[ -]nous|on est|est[ -]on|est[ -]ce|c est)"
        r"(?: aujourd hui)?|on est quel jour(?: aujourd hui)?"
        r"|quelle (?:est la )?date(?: sommes[ -]nous| aujourd hui| d aujourd hui"
        r"| on est)?|(?:quelle est )?la date d aujourd hui"
        r"|c est quel jour(?: aujourd hui)?|nous sommes quel jour"
    ),
    bateria=(
        r"(?:combien de |niveau de (?:la )?|quel est le niveau de (?:la )?"
        r"|etat de la )?batterie(?: restante)?|il reste combien de batterie"
        r"|combien de batterie (?:il reste|reste[ -]t[ -]il)|ou en est la batterie"
    ),
    bloquear=(
        r"(?:verrouille|verrouiller|verrouillez|bloque|bloquer|bloquez)"
        r" (?:l |le |la |mon |ma )?(?:ordinateur|ordi|pc|ecran|portable|session)"
    ),
    vol_nome=r"(?:le |du )?(?:volume|son)",
    vol_sobe=r"(?:monte|monter|montez|augmente|augmenter|augmentez|hausse|remonte)",
    vol_desce=(
        r"(?:baisse|baisser|baissez|diminue|diminuer|diminuez|reduis|reduire"
        r"|reduisez)"
    ),
    vol_frases=(
        (r"(?:mets |mettre )?(?:le )?(?:son|volume) plus fort|plus fort", "up"),
        (r"(?:mets |mettre )?(?:le )?(?:son|volume) moins fort|moins fort", "down"),
    ),
    vol_definir=(
        r"(?:(?:mets|met|mettre|regle|regler|reglez|passe|ajuste|monte|baisse) )?"
        r"(?:le )?(?:volume|son) (?:a|au|sur)"
        r" (?P<n>\d{1,3}|maximum|max|minimum|min|zero)(?: ?%| pour ?cent)?"
    ),
    vol_niveis={"maximum": 100, "max": 100, "minimum": 0, "min": 0, "zero": 0},
    intensidade={
        "": _CN,
        "un peu": _CS,
        "un petit peu": _CS,
        "un peu plus": _CS,
        "legerement": _CS,
        "beaucoup": _CB,
    },
    vol_max=frozenset({"au maximum", "au max", "a fond"}),
    vol_min=frozenset({"au minimum", "au min", "a zero"}),
    mudo=(
        r"(?:coupe|couper|coupez) le son|(?:remets|remettre|remettez|retablis) le son"
        r"|(?:mets|mettre|mettez) (?:le son )?en sourdine|sourdine|enleve la sourdine"
    ),
    midia_alternar=(
        r"(?:pause|mets pause|mets en pause|mettre en pause|reprends|reprendre"
        r"|lecture|play)(?: (?:la |le |de la |du )?(?:musique|chanson|video|morceau))?"
        r"|(?:joue|relance|arrete|arreter|stop|stoppe) (?:la |le )?"
        r"(?:musique|chanson|video|morceau)"
    ),
    midia_proxima=(
        r"(?:(?:la |le )?(?:chanson|morceau|piste|video) )?suivante?"
        r"|(?:passe|saute|passer|sauter)(?: (?:a la |au |la |le |cette |ce )?"
        r"(?:chanson|morceau|piste|video|suivante|suivant))?"
        r"|(?:mets|joue) (?:la |le )?suivante?"
    ),
    midia_anterior=(
        r"(?:(?:la |le )?(?:chanson|morceau|piste|video) )?precedente?"
        r"|(?:reviens|retourne|revenir) (?:a la |au )(?:chanson |morceau |piste )?"
        r"precedente?"
    ),
    abrir=(
        r"(?:ouvre|ouvrir|ouvrez|lance|lancer|lancez|demarre|demarrer|demarrez)"
        r" (?:le |la |les |l |mon |ma |mes )?(?P<t>.+)"
    ),
    abrir_limpa=(
        r"^(?:(?:appli|application|app|programme|site)(?: de| du| d)? )"
        r"|(?: appli| application| app)$"
    ),
    apps={
        "bloc-notes": "bloco de notas",
        "bloc notes": "bloco de notas",
        "calculatrice": "calculadora",
        "explorateur de fichiers": "explorador de arquivos",
        "explorateur": "explorador de arquivos",
        "fichiers": "explorador de arquivos",
        "mes fichiers": "explorador de arquivos",
        "parametres": "configuracoes",
        "reglages": "configuracoes",
        "gestionnaire des taches": "gerenciador de tarefas",
        "gestionnaire de taches": "gerenciador de tarefas",
        "invite de commandes": "terminal",
        "navigateur": "navegador",
        "messagerie": "gmail",
        "mail": "gmail",
        "courriel": "gmail",
    },
    pesquisar=(
        r"(?:cherche|chercher|cherchez|recherche|rechercher|recherchez)"
        r"(?: des?| du)? (?P<q>.+?) sur (?P<s>google|youtube)",
        r"(?:cherche|recherche) sur (?P<s>google|youtube) (?P<q>.+)",
    ),
    energia=(
        (r"(?:eteins|eteindre|eteignez|eteint) " + _FR_PC, "shutdown"),
        (r"(?:redemarre|redemarrer|redemarrez) " + _FR_PC, "restart"),
        (
            r"(?:mets|mettre|mettez) " + _FR_PC + r" en veille|mise en veille"
            r"|(?:mets|mettre) en veille",
            "suspend",
        ),
        (
            r"(?:annule|annuler|annulez) (?:l |le )?(?:extinction|arret|redemarrage)",
            "abort",
        ),
    ),
    confirmar=(
        r"oui|oui je confirme|je confirme|confirme|je le confirme|vas[ -]y"
        r"|allez[ -]y|d accord|oui vas[ -]y|bien sur"
    ),
    negar=r"non|annule|annuler|laisse tomber|oublie|non merci|surtout pas|ne fais rien",
    desfazer=r"(?:annule|annuler|defais|defaire) (?:le )?rangement",
    timer=(
        r"(?:(?:mets|met|lance|demarre|cree|regle|programme) )?(?:un )?"
        r"(?:minuteur|timer|chrono|chronometre|compte a rebours)"
        r"(?: de| pour| d)? (?P<d>.+)"
    ),
    alarme=(
        r"(?:(?:mets|met|regle|programme|cree) )?(?:une |un )?(?:alarme|reveil)"
        r"(?: pour| a)? (?P<w>.+)|reveille[ -]moi(?: a)? (?P<w2>.+)"
    ),
    lembrar=(
        r"(?:rappelle[ -]moi|rappelez[ -]moi|fais[ -]moi penser|previens[ -]moi"
        r"|n oublie pas de me rappeler)(?: de| d| que| qu)?"
    ),
    conector=r"(?:de|d|que|qu) ",
    vago=r"(?:ca|cela|ceci|quelque chose|ce que|de ca|de cela)\b",
    quando_inicio=(
        r"(?:dans|d ici|a|vers|aujourd hui|demain|apres-demain|apres demain|midi"
        r"|minuit|ce soir)\b"
    ),
    em=r"(?:dans|d ici)",
    numeros={
        "un": 1,
        "une": 1,
        "deux": 2,
        "trois": 3,
        "quatre": 4,
        "cinq": 5,
        "six": 6,
        "sept": 7,
        "huit": 8,
        "neuf": 9,
        "dix": 10,
        "onze": 11,
        "douze": 12,
        "quinze": 15,
        "vingt": 20,
        "trente": 30,
        "quarante": 40,
        "quarante cinq": 45,
        "cinquante": 50,
        "soixante": 60,
    },
    unidades={
        "seconde": 1,
        "secondes": 1,
        "sec": 1,
        "minute": 60,
        "minutes": 60,
        "min": 60,
        "heure": 3600,
        "heures": 3600,
        "h": 3600,
    },
    e=" et ",
    meia_hora=r"(?:une )?demi heure",
    hora_e_meia=r"(?P<n><NUM>) heures? et demie",
    relogio=(
        r"(?:(?P<day>aujourd hui|demain|apres-demain|apres demain|ce soir) )?"
        r"(?:(?:a|vers|pour) )?"
        r"(?:(?P<noon>midi|minuit)"
        r"|(?P<h><NUM>)(?: ?h ?(?P<m>\d{2})?| heures?(?: (?P<mw>\d{1,2}|et demie"
        r"|et quart))?)?"
        r"(?: (?P<per>du matin|de l apres-midi|de l apres midi|du soir"
        r"|de la nuit))?)"
        r"(?: (?P<day2>aujourd hui|demain|ce soir))?"
    ),
    dias={
        "aujourd hui": "hoje",
        "demain": "amanha",
        "apres-demain": "depois de amanha",
        "apres demain": "depois de amanha",
        "ce soir": "hoje",
    },
    meio={"midi": "meio dia", "minuit": "meia noite"},
    periodos={
        "du matin": " da manha",
        "de l apres-midi": " da tarde",
        "de l apres midi": " da tarde",
        "du soir": " da noite",
        "de la nuit": " da madrugada",
    },
    minutos_palavra={"et demie": 30, "et quart": 15},
    dia_noite=frozenset({"ce soir"}),
)

_LINGUAS: dict[str, _Lingua] = {"en": _EN, "es": _ES, "fr": _FR}
IDIOMAS = tuple(_LINGUAS)

# ---------------------------------------------------------------------------
# Números, durações e horários
# ---------------------------------------------------------------------------


def _alternativas(palavras) -> str:
    return "|".join(re.escape(p) for p in sorted(palavras, key=len, reverse=True))


def _num_re(lingua: _Lingua) -> str:
    return r"(?:\d{1,3}|" + _alternativas(lingua.numeros) + r")"


def _hora_re(lingua: _Lingua) -> str:
    # Só palavras de 1 a 12 com mais de 2 letras: "a"/"un" não viram hora.
    palavras = [p for p, v in lingua.numeros.items() if 1 <= v <= 12 and len(p) > 2]
    return r"(?:\d{1,2}|" + _alternativas(palavras) + r")"


def _numero(s: str, lingua: _Lingua) -> Optional[int]:
    s = s.strip()
    if s.isdigit():
        return int(s)
    return lingua.numeros.get(s)


def _duracao(s: str, lingua: _Lingua) -> Optional[timedelta]:
    """'10 minutes', 'media hora', 'une heure et demie', '2 hours and 15 minutes'."""
    s = re.sub(r"\s+", " ", s.replace("-", " ")).strip()
    if re.fullmatch(lingua.meia_hora, s):
        return timedelta(minutes=30)
    num = _num_re(lingua)
    m = re.fullmatch(lingua.hora_e_meia.replace("<NUM>", num), s)
    if m:
        n = _numero(m.group("n") or m.groupdict().get("n2") or "", lingua)
        return timedelta(hours=n, minutes=30) if n is not None else None
    unidades = _alternativas(lingua.unidades)
    m = re.fullmatch(
        rf"(?P<n>{num}) (?P<u>{unidades})"
        rf"(?:,?{lingua.e}(?P<n2>{num}) (?P<u2>{unidades}))?",
        s,
    )
    if not m:
        return None
    total = 0
    for n_key, u_key in (("n", "u"), ("n2", "u2")):
        if m.group(n_key) is None:
            continue
        n = _numero(m.group(n_key), lingua)
        if n is None:
            return None
        total += n * lingua.unidades[m.group(u_key)]
    return timedelta(seconds=total) if total > 0 else None


def _relogio(
    s: str, lingua: _Lingua, now: Optional[datetime] = None, *, morning: bool = False
) -> Optional[datetime]:
    """'at 3 pm', 'a las 8 de la manana', 'demain a 15h30' -> próxima ocorrência.

    Monta o mesmo horário em português e usa ``tempo.parse_clock``, para valer
    a mesma regra do dia a dia ("às 3" é à tarde; alarme "às 6" é de manhã).
    """
    m = re.fullmatch(lingua.relogio.replace("<NUM>", _hora_re(lingua)), s.strip())
    if not m:
        return None
    grupos = m.groupdict()
    dia_txt = grupos.get("day") or grupos.get("day2") or ""
    if grupos.get("noon"):
        relogio = lingua.meio[grupos["noon"]]
    else:
        hora = _numero(grupos["h"], lingua)
        if hora is None:
            return None
        minutos: Optional[int] = 0
        if grupos.get("m"):
            minutos = int(grupos["m"])
        elif grupos.get("mw"):
            mw = grupos["mw"]
            minutos = int(mw) if mw.isdigit() else lingua.minutos_palavra.get(mw)
        if minutos is None or minutos > 59:
            return None
        periodo = lingua.periodos.get(grupos.get("per") or "", "")
        if not periodo and dia_txt in lingua.dia_noite:
            periodo = " da noite"
        relogio = f"{hora}" + (f"h{minutos:02d}" if minutos else "") + periodo
    dia = lingua.dias.get(dia_txt, "")
    texto_pt = (f"{dia} " if dia else "") + f"as {relogio}"
    return parse_clock(texto_pt, now, morning=morning)


def _quando(
    s: str, lingua: _Lingua, now: Optional[datetime] = None
) -> Optional[datetime]:
    """'in 10 minutes', 'dentro de media hora', 'dans 5 minutes', ou um horário."""
    now = now or datetime.now()
    m = re.fullmatch(lingua.em + r" (?P<d>.+)", s.strip())
    if m:
        duracao = _duracao(m.group("d"), lingua)
        return now + duracao if duracao else None
    return _relogio(s, lingua, now)


# ---------------------------------------------------------------------------
# Reconhecedores
# ---------------------------------------------------------------------------


def _aparar(t: str, where: list[int], lingua: _Lingua) -> tuple[str, list[int]]:
    """Tira as gentilezas do idioma ("can you ... please"), mantendo o mapa."""
    start, end = 0, len(t)
    m = re.match(lingua.prefixo, t)
    if m:
        start = m.end()
    while start < end and t[start] == " ":
        start += 1
    m = re.search(lingua.sufixo, t[start:end])
    if m:
        end = start + m.start()
    return t[start:end], where[start:end]


def _volume(t: str, lingua: _Lingua) -> Optional[Action]:
    up: Optional[bool] = None
    rest = ""
    m = re.fullmatch(
        rf"(?P<dir>{lingua.vol_sobe}|{lingua.vol_desce}) {lingua.vol_nome}"
        r"(?: (?P<rest>.+))?",
        t,
    )
    if m:
        up = re.fullmatch(lingua.vol_sobe, m.group("dir")) is not None
        rest = m.group("rest") or ""
    elif lingua.vol_depois:
        m = re.fullmatch(lingua.vol_depois, t)
        if m:
            up = m.group("sobe") is not None
            rest = m.group("rest") or ""
    if up is not None:
        if rest in lingua.vol_max and up:
            return Action("volume", "set", 100)
        if rest in lingua.vol_min and not up:
            return Action("volume", "set", 0)
        if rest in lingua.intensidade:
            return Action("volume", "up" if up else "down", lingua.intensidade[rest])
        # "sube el volumen al 80": cai no "definir" abaixo.
    for padrao, op in lingua.vol_frases:
        if re.fullmatch(padrao, t):
            return Action("volume", op, STEP_NORMAL)
    m = re.fullmatch(lingua.vol_definir, t)
    if m:
        n = m.group("n")
        nivel = lingua.vol_niveis.get(n)
        if nivel is None:
            nivel = int(n)
        return Action("volume", "set", nivel) if 0 <= nivel <= 100 else None
    if re.fullmatch(lingua.mudo, t):
        return Action("volume", "mute")
    return None


def _midia(t: str, lingua: _Lingua) -> Optional[Action]:
    if re.fullmatch(lingua.midia_alternar, t):
        return Action("media", "toggle")
    if re.fullmatch(lingua.midia_proxima, t):
        return Action("media", "next")
    if re.fullmatch(lingua.midia_anterior, t):
        return Action("media", "prev")
    return None


def _abrir(t: str, lingua: _Lingua) -> Optional[Action]:
    m = re.fullmatch(lingua.abrir, t)
    if not m:
        return None
    alvo = re.sub(lingua.abrir_limpa, "", m.group("t")).strip()
    chave = lingua.apps.get(alvo, alvo)
    return Action("open", target=chave) if chave in APPS else None


def _pesquisar(t: str, lingua: _Lingua) -> Optional[Action]:
    for padrao in lingua.pesquisar:
        m = re.fullmatch(padrao, t)
        if m:
            return Action("search", target=m.group("q"), site=m.group("s"))
    return None


def _info(t: str, lingua: _Lingua) -> Optional[Action]:
    if re.fullmatch(lingua.hora, t):
        return Action("time")
    if re.fullmatch(lingua.data, t):
        return Action("date")
    if re.fullmatch(lingua.bateria, t):
        return Action("battery")
    if re.fullmatch(lingua.bloquear, t):
        return Action("lock")
    return None


def _energia(t: str, lingua: _Lingua) -> Optional[Action]:
    for padrao, op in lingua.energia:
        if re.fullmatch(padrao, t):
            return Action("power", op=op)
    if re.fullmatch(lingua.desfazer, t):
        return Action("organize_undo")
    return None


def _confirmacao(t: str, lingua: _Lingua) -> Optional[Action]:
    """Só vale com uma ação pendente; fora disso é conversa comum."""
    if confirmacao.pending() is None:
        return None
    if re.fullmatch(lingua.confirmar, t):
        return Action("confirm")
    if re.fullmatch(lingua.negar, t):
        return Action("deny")
    return None


def _timer(t: str, lingua: _Lingua) -> Optional[Action]:
    for padrao in (lingua.timer, lingua.timer_antes):
        if not padrao:
            continue
        m = re.fullmatch(padrao, t)
        if m:
            duracao = _duracao(m.group("d"), lingua)
            if duracao is not None:
                return Action(
                    "remind", target=_TIMER_TEXT, when=datetime.now() + duracao
                )
    m = re.fullmatch(lingua.alarme, t)
    if m:
        alvo = m.group("w") or m.group("w2") or ""
        when = _relogio(alvo, lingua, morning=True) or _quando(alvo, lingua)
        if when is not None:
            return Action("remind", target=_ALARM_TEXT, when=when)
    return None


def _lembrete(text: str, t: str, where: list[int], lingua: _Lingua) -> Optional[Action]:
    """'remind me to call mom at 3 pm', 'recuérdame en 10 minutos llamar a mamá'."""
    m = re.match(lingua.lembrar + r" ", t)
    if not m:
        return None
    rest_start = m.end()
    rest = t[rest_start:]
    words = rest.split()
    starts = [rest_start + w.start() for w in re.finditer(r"\S+", rest)]
    if not words:
        return None
    found = None
    # Quando no fim: "... at 3 pm".
    for i in range(1, len(words)):
        piece = " ".join(words[i:])
        if not re.match(lingua.quando_inicio, piece):
            continue
        when = _quando(piece, lingua)
        if when is not None:
            found = (rest_start, starts[i] - 1, when)
            break
    if found is None:
        # Quando no começo: "in 10 minutes to call mom".
        for i in range(len(words) - 1, 0, -1):
            piece = " ".join(words[:i])
            if not re.match(lingua.quando_inicio, piece):
                continue
            when = _quando(piece, lingua)
            if when is not None:
                found = (starts[i], len(t), when)
                break
    if found is None:
        return None
    what_start, what_end, when = found
    cm = re.match(lingua.conector, t[what_start:what_end])
    if cm:
        what_start += cm.end()
    if re.match(lingua.vago, t[what_start:what_end]):
        return None
    what = original_text(text, where, what_start, what_end)
    if not what:
        return None
    return Action("remind", target=what, when=when)


# ---------------------------------------------------------------------------
# Mandar a agenda para o Google Agenda / Outlook
# ---------------------------------------------------------------------------

# idioma -> (verbo, objeto "tudo", objeto "o último", preposição, calendários)
# Calendários: (padrão, destino); "" = o padrão da config.
_ENVIO: dict[str, tuple[str, str, str, str, tuple[tuple[str, str], ...]]] = {
    "en": (
        r"(?:send|put|add|export|save)",
        r"(?:everything|all|all of them|my appointments|my schedule|my agenda"
        r"|my events|all my appointments|them)",
        r"(?:it|this|that|the appointment|the meeting|the event|the last one)",
        r"(?:to|in|into|on)",
        (
            (r"(?:my |the )?google calendar", "google"),
            (
                r"(?:my |the )?(?:work|office|school) outlook"
                r"|(?:my |the )?outlook (?:for work|at work|365|calendar for work)",
                "outlook_trabalho",
            ),
            (r"(?:my |the )?outlook(?: calendar)?", "outlook"),
            (r"(?:my |the )?windows calendar", "windows"),
            (r"(?:my |the )?calendar", ""),
        ),
    ),
    "es": (
        r"(?:manda|mandalo|mandala|envia|envialo|enviala|pasa|pasalo|agrega|agregalo"
        r"|anade|anadelo|pon|ponlo|exporta|guarda)",
        r"(?:todo|todos|mis citas|mis compromisos|mi agenda|mis eventos)",
        r"(?:eso|esto|la cita|la reunion|el evento|el compromiso|el ultimo)",
        r"(?:a|al|en|a la)",
        (
            (r"(?:mi |el )?(?:google calendar|calendario de google)", "google"),
            (
                r"(?:mi |el )?outlook (?:del trabajo|de la empresa|de la escuela|365)",
                "outlook_trabalho",
            ),
            (r"(?:mi |el )?(?:outlook|calendario de outlook)", "outlook"),
            (r"(?:mi |el )?calendario de windows", "windows"),
            (r"(?:mi |el )?calendario", ""),
        ),
    ),
    "fr": (
        r"(?:envoie|envoyer|mets|mettre|ajoute|ajouter|exporte|enregistre)",
        r"(?:tout|tous|mes rendez[ -]vous|mon agenda|mes evenements)",
        r"(?:ca|le|la|ce rendez[ -]vous|le rendez[ -]vous|la reunion|l evenement"
        r"|le dernier)",
        r"(?:a|dans|sur|vers)",
        (
            (r"(?:mon |le )?google (?:agenda|calendar)", "google"),
            (
                r"(?:mon |le )?outlook (?:du travail|pro|professionnel|de l ecole|365)",
                "outlook_trabalho",
            ),
            (r"(?:mon |le )?(?:outlook|calendrier outlook)", "outlook"),
            (r"(?:mon |le )?calendrier (?:de )?windows", "windows"),
            (r"(?:mon |le )?(?:calendrier|agenda)", ""),
        ),
    ),
}


def _agenda_envio(t: str, codigo: str) -> Optional[Action]:
    """'send it to Google Calendar', 'manda todo a Outlook', 'envoie ça à
    Google Agenda': manda o último compromisso (ou todos) para o calendário."""
    regras = _ENVIO.get(codigo)
    if regras is None:
        return None
    verbo, todos, ultimo, prep, calendarios = regras
    m = re.fullmatch(
        verbo
        + r"(?: (?P<obj>"
        + todos
        + "|"
        + ultimo
        + r"))? "
        + prep
        + r" (?P<cal>.+)",
        t,
    )
    if not m:
        return None
    for padrao, destino in calendarios:
        if re.fullmatch(padrao, m.group("cal")):
            obj = m.group("obj") or ""
            site = "todos" if obj and re.fullmatch(todos, obj) else ""
            if obj and not site:
                site = "ultimo"
            return Action("agenda_export", op=destino, site=site)
    return None


def parse(text: str, t: str, where: list[int], codigo: str) -> Optional[Action]:
    """Comando em inglês, espanhol ou francês; None se não for um.

    ``t``/``where`` vêm de ``intencoes.clean_with_map(text)``.
    """
    lingua = _LINGUAS.get(codigo)
    if lingua is None:
        return parse_exato(text, codigo)
    t, where = _aparar(t, where, lingua)
    if not t:
        return None
    for simples in (_confirmacao, _energia, _timer):
        action = simples(t, lingua)
        if action is not None:
            return action
    action = _agenda_envio(t, codigo)
    if action is not None:
        return action
    action = _lembrete(text, t, where, lingua)
    if action is not None or len(t) > 80:
        return action
    for simples in (_volume, _midia, _abrir, _pesquisar, _info):
        action = simples(t, lingua)
        if action is not None:
            return action
    return None


# ---------------------------------------------------------------------------
# Chinês, hindi e árabe: só as palavras que as respostas pedem
# ---------------------------------------------------------------------------

_EXATAS: dict[str, dict[str, frozenset[str]]] = {
    "zh": {
        "confirm": frozenset({"确认", "我确认", "确定"}),
        "deny": frozenset({"取消", "不", "不要", "算了", "不用了"}),
        "abort": frozenset({"取消关机", "取消重启"}),
    },
    "hi": {
        "confirm": frozenset(
            {"पुष्टि", "पुष्टि करें", "पुष्टि करो", "पुष्टि करता हूँ", "पुष्टि करती हूँ", "हाँ"}
        ),
        "deny": frozenset({"नहीं", "रद्द करें", "रद्द करो", "रहने दो"}),
        "abort": frozenset(
            {"शटडाउन रद्द करो", "शटडाउन रद्द करें", "रीस्टार्ट रद्द करो", "रीस्टार्ट रद्द करें"}
        ),
    },
    "ar": {
        "confirm": frozenset({"أؤكد", "اؤكد", "تأكيد", "نعم", "نعم أؤكد"}),
        "deny": frozenset({"لا", "إلغاء", "الغاء", "لا تفعل"}),
        "abort": frozenset(
            {
                "إلغاء الإيقاف",
                "الغاء الايقاف",
                "إلغاء إعادة التشغيل",
                "الغاء اعادة التشغيل",
            }
        ),
    },
}
_PONTUACAO = re.compile(r"[\s.,!?;:。！？，、…\"'“”«»।؟،]+")


def parse_exato(text: str, codigo: str) -> Optional[Action]:
    """Confirmar, negar ou cancelar o desligamento, só com a frase exata."""
    tabela = _EXATAS.get(codigo)
    if tabela is None:
        return None
    frase = _PONTUACAO.sub(" ", text).strip()
    if frase in tabela["abort"]:
        return Action("power", op="abort")
    if confirmacao.pending() is None:
        return None
    if frase in tabela["confirm"]:
        return Action("confirm")
    if frase in tabela["deny"]:
        return Action("deny")
    return None


__all__ = ["IDIOMAS", "parse", "parse_exato"]
