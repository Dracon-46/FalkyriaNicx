"""Ações rápidas: reconhecimento de frases e execução (sem tocar no sistema)."""

from __future__ import annotations

import pytest

from nicx.acoes import handle, parse, sistema
from nicx.acoes.intencoes import STEP_BIG, STEP_NORMAL, STEP_SMALL, Action


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Aumenta o volume", Action("volume", "up", STEP_NORMAL)),
        ("Nicx, aumenta o volume por favor", Action("volume", "up", STEP_NORMAL)),
        # Frases reais dos testes de voz.
        ("Queria que você aumentasse o volume", Action("volume", "up", STEP_NORMAL)),
        ("Aumento o volume do computador", Action("volume", "up", STEP_NORMAL)),
        ("abaixa o som um pouco", Action("volume", "down", STEP_SMALL)),
        ("diminui o volume bastante", Action("volume", "down", STEP_BIG)),
        ("Som mais alto", Action("volume", "up", STEP_NORMAL)),
        ("Volume em 30%", Action("volume", "set", 30)),
        ("coloca o volume no máximo", Action("volume", "set", 100)),
        ("aumenta o volume no máximo", Action("volume", "set", 100)),
        ("volume em 150", None),
        ("Muta", Action("volume", "mute")),
        ("Pausa a música", Action("media", "toggle")),
        ("Próxima música", Action("media", "next")),
        ("Música anterior", Action("media", "prev")),
        ("Abre o YouTube", Action("open", target="youtube")),
        ("abre o site do github", Action("open", target="github")),
        ("Abre o bloco de notas", Action("open", target="bloco de notas")),
        (
            "Pesquisa receita de bolo no YouTube",
            Action("search", target="receita de bolo", site="youtube"),
        ),
        ("Que horas são?", Action("time")),
        ("Que dia é hoje?", Action("date")),
        ("Quanto de bateria tem?", Action("battery")),
        ("Bloqueia o computador", Action("lock")),
    ],
)
def test_parse_commands(text, expected):
    assert parse(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Como eu aumento o volume do Windows?",
        "Qual o clima de hoje?",
        "Abre a porta da geladeira",
        "E aí!",
        "Falkyria",
        "Para",
        "aumenta o volume do contador",
        "Pesquisa receita de bolo",
        "",
        "abre " + "x" * 100,
    ],
)
def test_parse_leaves_questions_to_the_model(text):
    assert parse(text) is None


@pytest.fixture
def keys(monkeypatch):
    pressed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        sistema, "_press", lambda vk, times=1: pressed.append((vk, times))
    )
    monkeypatch.setattr(sistema.sys, "platform", "win32")
    return pressed


def test_volume_up_presses_volume_key(keys):
    outcome = handle("aumenta o volume")
    assert outcome is not None and outcome.ok
    assert keys == [(sistema._VK_VOLUME_UP, STEP_NORMAL)]


def test_volume_set_goes_to_zero_then_up(keys):
    outcome = handle("volume em 30%")
    assert outcome.message == "Volume em 30%."
    assert keys == [(sistema._VK_VOLUME_DOWN, 50), (sistema._VK_VOLUME_UP, 15)]


def test_media_toggle(keys):
    assert handle("pausa a música").ok
    assert keys == [(sistema._VK_MEDIA_PLAY_PAUSE, 1)]


def test_volume_outside_windows_explains(monkeypatch):
    monkeypatch.setattr(sistema.sys, "platform", "linux")
    outcome = handle("aumenta o volume")
    assert not outcome.ok
    assert "Windows" in outcome.message


def test_open_url_uses_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(sistema.webbrowser, "open", opened.append)
    outcome = handle("abre o youtube")
    assert outcome.message == "Abrindo o YouTube."
    assert opened == ["https://www.youtube.com"]


def test_open_missing_program_says_so(monkeypatch):
    monkeypatch.setattr(sistema.sys, "platform", "win32")

    def fail(_target):
        raise OSError("not found")

    monkeypatch.setattr(sistema, "_start", fail)
    monkeypatch.setattr(sistema.shutil, "which", lambda _name: None)
    outcome = handle("abre o word")
    assert not outcome.ok
    assert outcome.message == "Não encontrei o Word neste computador."


def test_search_builds_query_url(monkeypatch):
    opened = []
    monkeypatch.setattr(sistema.webbrowser, "open", opened.append)
    handle("pesquisa bolo de cenoura no google")
    assert opened == ["https://www.google.com/search?q=bolo+de+cenoura"]


def test_time_and_date_are_spoken_in_portuguese(monkeypatch):
    import datetime as dt

    class Fixed(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 23, 21, 5)

    monkeypatch.setattr(sistema, "datetime", Fixed)
    assert handle("que horas são").message == "São 21h05."
    assert handle("que dia é hoje").message == "Hoje é sexta-feira, 23 de outubro."


def test_battery_without_sensor(monkeypatch):
    import psutil

    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)
    assert (
        handle("quanto de bateria tem").message
        == "Não encontrei bateria neste computador."
    )


def test_failures_never_raise(monkeypatch):
    def boom(_action):
        raise RuntimeError("x")

    monkeypatch.setattr(sistema, "_volume", boom)
    outcome = handle("aumenta o volume")
    assert not outcome.ok
    assert outcome.message == "Não consegui fazer isso agora."


def test_tool_runs_same_actions(keys):
    from nicx.acoes.ferramenta import ComputerControlTool

    tool = ComputerControlTool()
    assert tool.spec.name == "controle_pc"
    result = tool.execute(acao="volume_definir", valor=40)
    assert result.success and result.content == "Volume em 40%."
    unknown = tool.execute(acao="abrir", alvo="geladeira")
    assert not unknown.success and "Sei abrir" in unknown.content
    assert not tool.execute(acao="formatar_disco").success
