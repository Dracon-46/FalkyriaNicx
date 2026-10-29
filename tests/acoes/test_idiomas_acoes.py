"""Ações rápidas no idioma da interface: entender e responder em cada idioma."""

from __future__ import annotations

import string
from datetime import datetime, timedelta

import pytest

from nicx.acoes import confirmacao, executores, handle, parse, run, sistema, textos
from nicx.acoes.intencoes import STEP_NORMAL, STEP_SMALL, Action

NOW = datetime(2026, 10, 27, 14, 10)


@pytest.fixture(autouse=True)
def nicx_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"
    confirmacao.drop()


@pytest.fixture
def keys(monkeypatch):
    pressed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        sistema, "_press", lambda vk, times=1: pressed.append((vk, times))
    )
    monkeypatch.setattr(sistema.sys, "platform", "win32")
    return pressed


@pytest.fixture
def friday_night(monkeypatch):
    import datetime as dt

    class Fixed(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 23, 21, 5)

    monkeypatch.setattr(sistema, "datetime", Fixed)


@pytest.fixture
def commands(monkeypatch):
    import psutil  # noqa: F401 - antes de trocar sys.platform

    ran: list[list[str]] = []
    monkeypatch.setattr(executores.sys, "platform", "win32")
    monkeypatch.setattr(
        executores.subprocess, "run", lambda cmd, **_kw: ran.append(list(cmd))
    )
    return ran


# ---------------------------------------------------------------------------
# Entender
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "text", "expected"),
    [
        ("en", "What time is it?", Action("time")),
        ("en", "Hey Nicx, what's the date today?", Action("date")),
        ("en", "can you turn up the volume please", Action("volume", "up", 5)),
        ("en", "turn the volume down a bit", Action("volume", "down", STEP_SMALL)),
        ("en", "set the volume to 40%", Action("volume", "set", 40)),
        ("en", "mute", Action("volume", "mute")),
        ("en", "pause the music", Action("media", "toggle")),
        ("en", "next song", Action("media", "next")),
        ("en", "previous track", Action("media", "prev")),
        ("en", "open YouTube", Action("open", target="youtube")),
        ("en", "open the calculator", Action("open", target="calculadora")),
        (
            "en",
            "search cat videos on youtube",
            Action("search", target="cat videos", site="youtube"),
        ),
        ("en", "how much battery do I have", Action("battery")),
        ("en", "lock the screen", Action("lock")),
        ("es", "¿Qué hora es?", Action("time")),
        ("es", "qué día es hoy", Action("date")),
        ("es", "sube el volumen", Action("volume", "up", STEP_NORMAL)),
        ("es", "baja el volumen un poco", Action("volume", "down", STEP_SMALL)),
        ("es", "sube el volumen al 80", Action("volume", "set", 80)),
        ("es", "silencia", Action("volume", "mute")),
        ("es", "para la música", Action("media", "toggle")),
        ("es", "siguiente canción", Action("media", "next")),
        ("es", "abre la calculadora", Action("open", target="calculadora")),
        (
            "es",
            "busca recetas en google",
            Action("search", target="recetas", site="google"),
        ),
        ("es", "cuánta batería me queda", Action("battery")),
        ("es", "bloquea la pantalla", Action("lock")),
        ("fr", "Quelle heure est-il ?", Action("time")),
        ("fr", "quel jour sommes-nous", Action("date")),
        ("fr", "monte le son", Action("volume", "up", STEP_NORMAL)),
        ("fr", "mets le volume à 50 %", Action("volume", "set", 50)),
        ("fr", "coupe le son", Action("volume", "mute")),
        ("fr", "mets en pause", Action("media", "toggle")),
        ("fr", "chanson précédente", Action("media", "prev")),
        ("fr", "lance l'explorateur", Action("open", target="explorador de arquivos")),
        (
            "fr",
            "cherche des recettes sur youtube",
            Action("search", target="recettes", site="youtube"),
        ),
        ("fr", "niveau de batterie", Action("battery")),
        ("fr", "verrouille l'écran", Action("lock")),
    ],
)
def test_parse_other_languages(idioma, text, expected):
    assert parse(text, idioma) == expected


@pytest.mark.parametrize(
    ("idioma", "text"),
    [
        ("en", "how do I turn up the volume?"),
        ("en", "what is the capital of France?"),
        ("en", "open the door"),
        ("en", "remind me about it"),
        ("es", "¿cuál es la capital de Francia?"),
        ("fr", "quelle est la capitale de la France ?"),
        # Chinês, hindi e árabe vão para o modelo.
        ("zh", "现在几点了？"),
        ("zh", "打开YouTube"),
        ("hi", "अभी कितने बजे हैं?"),
        ("ar", "كم الساعة الآن؟"),
    ],
)
def test_questions_and_unparsed_languages_go_to_the_model(idioma, text):
    assert parse(text, idioma) is None
    assert handle(text, idioma) is None


def test_portuguese_mode_ignores_other_languages():
    assert parse("what time is it") is None
    assert parse("sube el volumen", "pt-BR") is None
    assert parse("quelle heure est-il") is None


def test_portuguese_still_works_with_another_interface_language():
    assert parse("que horas são", "en") == Action("time")
    assert parse("aumenta o volume", "fr") == Action("volume", "up", STEP_NORMAL)


@pytest.mark.parametrize(
    ("idioma", "text", "target", "hour"),
    [
        ("en", "remind me to call mom at 3 pm", "call mom", 15),
        ("en", "remind me tomorrow at 8 am to buy bread", "buy bread", 8),
        ("es", "recuérdame llamar a mamá a las 3 de la tarde", "llamar a mamá", 15),
        ("fr", "rappelle-moi d'appeler maman à 15h30", "appeler maman", 15),
    ],
)
def test_reminders_keep_the_original_text(idioma, text, target, hour):
    action = parse(text, idioma)
    assert action is not None and action.kind == "remind"
    assert action.target == target
    assert action.when is not None and action.when.hour == hour


@pytest.mark.parametrize(
    ("idioma", "text", "minutes"),
    [
        ("en", "set a timer for 10 minutes", 10),
        ("en", "set a 5 minute timer", 5),
        ("en", "start a timer for an hour and a half", 90),
        ("es", "pon un temporizador de media hora", 30),
        ("fr", "mets un minuteur de dix minutes", 10),
        ("fr", "minuteur d'une demi-heure", 30),
    ],
)
def test_timers(idioma, text, minutes):
    before = datetime.now()
    action = parse(text, idioma)
    assert action is not None and action.target == "o tempo acabou"
    delta = action.when - before
    assert timedelta(minutes=minutes) <= delta < timedelta(minutes=minutes, seconds=5)


def test_alarm_in_english_is_in_the_morning():
    action = parse("set an alarm for 7 am", "en")
    assert action.target == "alarme"
    assert (action.when.hour, action.when.minute) == (7, 0)


# ---------------------------------------------------------------------------
# Responder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "text", "hora", "data"),
    [
        ("pt-BR", "que horas são", "São 21h05.", "Hoje é sexta-feira, 23 de outubro."),
        ("en", "what time is it", "It's 9:05 PM.", "Today is Friday, October 23."),
        ("es", "qué hora es", "Son las 21:05.", "Hoy es viernes, 23 de octubre."),
        (
            "fr",
            "quelle heure est-il",
            "Il est 21 h 05.",
            "Nous sommes le vendredi 23 octobre.",
        ),
    ],
)
def test_time_and_date_in_each_language(friday_night, idioma, text, hora, data):
    assert handle(text, idioma).message == hora
    assert run(Action("date"), idioma).message == data


def test_portuguese_answers_are_unchanged(friday_night):
    assert handle("que horas são").message == "São 21h05."
    assert handle("que horas são", "pt-BR").message == "São 21h05."
    assert handle("que horas são", None).message == "São 21h05."


def test_spanish_volume_answers_in_spanish(keys):
    outcome = handle("sube el volumen", "es")
    assert outcome.ok and outcome.message == "Subí el volumen."
    assert keys == [(sistema._VK_VOLUME_UP, STEP_NORMAL)]


def test_reply_follows_the_interface_even_for_portuguese_commands(keys):
    assert handle("aumenta o volume", "en").message == "Turned the volume up."
    assert handle("aumenta o volume", "zh").message == "已调高音量。"
    assert handle("aumenta o volume", "ar").message == "رفعت مستوى الصوت."


def test_open_uses_the_app_name_of_the_language(monkeypatch):
    monkeypatch.setattr(sistema.webbrowser, "open", lambda _url: None)
    monkeypatch.setattr(sistema, "_start", lambda _target: None)
    monkeypatch.setattr(sistema.sys, "platform", "win32")
    monkeypatch.setattr(sistema.shutil, "which", lambda name: name)
    assert handle("open youtube", "en").message == "Opening YouTube."
    assert handle("open the calculator", "en").message == "Opening Calculator."
    assert handle("abre la calculadora", "es").message == "Abriendo la Calculadora."
    assert handle("ouvre le bloc-notes", "fr").message == "J'ouvre le Bloc-notes."


def test_timer_answer_in_spanish():
    message = handle("pon un temporizador de 5 minutos", "es").message
    assert message == "Temporizador listo: te aviso en 5 minutos."


def test_failures_explain_in_the_language(monkeypatch):
    monkeypatch.setattr(sistema.sys, "platform", "linux")
    assert handle("turn up the volume", "en").message == (
        "I can only do that on Windows for now."
    )


@pytest.mark.parametrize(
    ("idioma", "alvo", "esperado"),
    [
        ("pt-BR", datetime(2026, 10, 28, 8, 0), "amanhã às 8h"),
        ("en", datetime(2026, 10, 28, 8, 0), "tomorrow at 8 AM"),
        ("en", datetime(2026, 10, 27, 15, 30), "at 3:30 PM"),
        ("es", datetime(2026, 10, 28, 8, 0), "mañana a las 8:00"),
        ("es", datetime(2026, 10, 28, 1, 0), "mañana a la 1:00"),
        ("fr", datetime(2026, 10, 28, 8, 0), "demain à 8 h"),
        ("fr", NOW + timedelta(minutes=20), "dans 20 minutes"),
        ("zh", datetime(2026, 10, 28, 8, 0), "明天 8:00"),
        ("en", datetime(2026, 11, 20, 9, 0), "on November 20 at 9 AM"),
    ],
)
def test_spoken_times(idioma, alvo, esperado):
    assert textos.quando(alvo, NOW, idioma) == esperado


def test_agenda_days():
    friday = datetime(2026, 10, 30, 9, 30)
    assert textos.dia(friday, NOW) == "sexta (30/10) às 9h30"
    assert textos.dia(friday, NOW, idioma="en") == "Friday (October 30) at 9:30 AM"
    assert textos.dia(friday, NOW, idioma="fr") == "vendredi (30/10) à 9 h 30"


# ---------------------------------------------------------------------------
# Confirmação de energia por idioma
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idioma", "pedido", "palavra", "resposta"),
    [
        ("pt-BR", "desliga o computador", "confirmo", "Desligando em 30 segundos"),
        ("en", "shut down the computer", "confirm", "Shutting down in 30 seconds"),
        ("es", "apaga el ordenador", "confirmo", "Apagando en 30 segundos"),
        ("fr", "éteins l'ordinateur", "je confirme", "Extinction dans 30 secondes"),
        ("zh", "desliga o computador", "确认", "30 秒后关机"),
        ("hi", "desliga o computador", "पुष्टि", "30 सेकंड में बंद हो रहा है"),
        ("ar", "desliga o computador", "أؤكد", "سيتم إيقاف التشغيل"),
    ],
)
def test_shutdown_confirmation_per_language(
    commands, idioma, pedido, palavra, resposta
):
    ask = handle(pedido, idioma).message
    # A pergunta pede a palavra do próprio idioma.
    assert palavra in ask
    assert commands == []
    assert handle(palavra, idioma).message.startswith(resposta)
    assert commands == [["shutdown", "/s", "/t", "30"]]
    # Vale uma vez só.
    assert parse(palavra, idioma) is None


@pytest.mark.parametrize(
    ("idioma", "palavra"),
    [("en", "confirm"), ("en", "yes"), ("es", "confirmo"), ("fr", "je confirme")],
)
def test_confirmation_word_does_nothing_without_a_pending_action(
    commands, idioma, palavra
):
    assert parse(palavra, idioma) is None
    assert handle(palavra, idioma) is None
    assert commands == []


def test_unrelated_answer_does_not_confirm(commands):
    handle("restart the computer", "en")
    assert handle("maybe later", "en") is None
    assert handle("ok", "en") is None
    assert commands == []
    assert confirmacao.pending() is not None


def test_english_confirm_word_is_not_accepted_in_portuguese(commands):
    handle("desliga o computador")
    assert parse("confirm") is None
    assert commands == []


@pytest.mark.parametrize(
    ("idioma", "nao", "resposta"),
    [
        ("en", "no", "All right, I won't do anything."),
        ("es", "no", "Está bien, no haré nada."),
        ("fr", "non", "D'accord, je ne fais rien."),
        ("zh", "取消", "好的，我什么都不做。"),
    ],
)
def test_saying_no_in_each_language(commands, idioma, nao, resposta):
    handle("reinicia o pc", idioma)
    assert handle(nao, idioma).message == resposta
    assert commands == []


@pytest.mark.parametrize(
    ("idioma", "texto_cancelar"),
    [
        ("en", "cancel the shutdown"),
        ("es", "cancela el apagado"),
        ("fr", "annule l'extinction"),
        ("zh", "取消关机"),
    ],
)
def test_abort_shutdown_in_each_language(commands, idioma, texto_cancelar):
    assert handle(texto_cancelar, idioma).ok
    assert commands == [["shutdown", "/a"]]


# ---------------------------------------------------------------------------
# Tabela de textos
# ---------------------------------------------------------------------------


def _campos(modelo: str) -> set[str]:
    return {nome for _, nome, _, _ in string.Formatter().parse(modelo) if nome}


def test_every_language_has_every_phrase():
    base = set(textos.FRASES["pt-BR"])
    for codigo, frases in textos.FRASES.items():
        assert set(frases) == base, codigo


def test_every_phrase_formats_in_every_language():
    # Valores que as frases recebem além dos do português: pedaços de data e
    # hora, e o nome no singular e no plural (cada idioma usa o que soa melhor).
    extras = {"a_las", "son_las", "hora", "h", "dd", "mm", "d", "mes", "semana", "dia"}
    extras |= {"nome", "nomes"}
    for chave, modelo_pt in textos.FRASES["pt-BR"].items():
        permitidos = _campos(modelo_pt) | extras
        for codigo, frases in textos.FRASES.items():
            campos = _campos(frases[chave])
            assert campos <= permitidos, (codigo, chave, campos - permitidos)
            frases[chave].format(**{c: "x" for c in campos})
