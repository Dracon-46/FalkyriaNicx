"""Agenda local: entender dias, marcar, ver, desmarcar e exportar."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from nicx.acoes import agenda, executores, handle, lembretes, parse
from nicx.acoes.tempo import parse_day, parse_moment, say_day

NOW = datetime(2026, 10, 28, 9, 0)  # uma quarta-feira


@pytest.fixture(autouse=True)
def nicx_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    # "manda pro calendário" segue o padrão da config: aqui, o do Windows.
    from types import SimpleNamespace

    from nicx.acoes import calendarios

    cfg = SimpleNamespace(calendario_padrao="windows", fuso="America/Sao_Paulo")
    monkeypatch.setattr(calendarios, "_config_agenda", lambda: cfg)
    return tmp_path / "home"


# ---------------------------------------------------------------------------
# Dias e momentos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hoje", date(2026, 10, 28)),
        ("amanha", date(2026, 10, 29)),
        ("sexta", date(2026, 10, 30)),
        ("na sexta-feira", date(2026, 10, 30)),
        ("quarta", date(2026, 10, 28)),
        ("proxima quarta", date(2026, 11, 4)),
        ("segunda que vem", date(2026, 11, 2)),
        ("dia 30", date(2026, 10, 30)),
        ("dia 3", date(2026, 11, 3)),  # dia 3 já passou: mês que vem
        ("30-10", date(2026, 10, 30)),
        ("5 de novembro", date(2026, 11, 5)),
        ("31-02", None),
        ("banana", None),
    ],
)
def test_parse_day(text, expected):
    assert parse_day(text, NOW) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sexta as 15h", (datetime(2026, 10, 30, 15, 0), True)),
        ("amanha as 3", (datetime(2026, 10, 29, 15, 0), True)),
        ("as 10 do dia 30", (datetime(2026, 10, 30, 10, 0), True)),
        ("dia 5 de novembro as 9 e meia", (datetime(2026, 11, 5, 9, 30), True)),
        ("para amanha ao meio dia", (datetime(2026, 10, 29, 12, 0), True)),
        ("sexta", (datetime(2026, 10, 30, 0, 0), False)),
        ("quando der", None),
    ],
)
def test_parse_moment(text, expected):
    assert parse_moment(text, NOW) == expected


def test_say_day():
    assert say_day(datetime(2026, 10, 28, 15, 0), NOW) == "hoje às 15h"
    assert say_day(datetime(2026, 10, 30, 9, 30), NOW) == "sexta (30/10) às 9h30"
    assert say_day(datetime(2026, 11, 20, 8, 0), NOW, with_time=False) == "dia 20/11"


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "target"),
    [
        ("Marca reunião com o João sexta às 15h", "agenda_add", "reunião com o João"),
        ("agenda dentista dia 30", "agenda_add", "dentista"),
        (
            "coloca na agenda almoço com a Ana amanhã ao meio-dia",
            "agenda_add",
            "almoço com a Ana",
        ),
        ("marca consulta no médico 05/11 às 9:30", "agenda_add", "consulta no médico"),
        ("o que eu tenho amanhã?", "agenda_list", ""),
        ("minha agenda da semana", "agenda_list", ""),
        ("quais são meus compromissos", "agenda_list", ""),
        ("desmarca a consulta", "agenda_cancel", "consulta"),
        ("cancela o próximo compromisso", "agenda_cancel", ""),
        ("manda pro calendário do Windows", "agenda_export", ""),
    ],
)
def test_parse_agenda_phrases(text, kind, target):
    action = parse(text)
    assert action is not None and action.kind == kind
    assert action.target == target


@pytest.mark.parametrize(
    "text",
    [
        "coloca música",
        "o que eu tenho na geladeira",
        "marca reunião",  # sem quando: o modelo pergunta
        "cancela o timer",  # é dos lembretes
    ],
)
def test_agenda_leaves_other_things_alone(text):
    action = parse(text)
    assert action is None or not action.kind.startswith("agenda")


def test_all_day_event_has_no_time():
    action = parse("agenda dentista dia 30")
    assert action.op == "dia"


# ---------------------------------------------------------------------------
# Marcar, ver, desmarcar
# ---------------------------------------------------------------------------


def _next_weekday_at(hour: int) -> datetime:
    start = datetime.now() + timedelta(days=2)
    return start.replace(hour=hour, minute=0, second=0, microsecond=0)


def test_add_creates_a_warning_15_minutes_before():
    when = _next_weekday_at(15)
    event = agenda.add("reunião com o João", when)
    reminders = lembretes.pending()
    assert [r.id for r in reminders] == [event.reminder_id]
    assert reminders[0].due_at == when - timedelta(minutes=15)
    assert reminders[0].text == "Daqui a 15 minutos: reunião com o João"


def test_flow_add_list_cancel():
    assert handle(
        "marca reunião com o João depois de amanhã às 15h"
    ).message.startswith("Marquei reunião com o João")
    handle("agenda dentista depois de amanhã")
    day_list = handle("o que eu tenho depois de amanhã").message
    assert "reunião com o João às 15h" in day_list and "dentista o dia todo" in day_list
    assert handle("desmarca a reunião com o João").message.startswith(
        "Desmarquei reunião com o João"
    )
    assert [e.title for e in agenda.upcoming(days=7)] == ["dentista"]
    # O aviso da reunião desmarcada também sai.
    assert all("João" not in r.text for r in lembretes.pending())


def test_past_time_is_refused():
    message = handle("marca café hoje às 0h01").message
    assert "já passou" in message
    assert agenda.upcoming(days=7) == []


def test_cancel_by_day_word():
    friday = parse_day("sexta")
    agenda.add(
        "reunião de equipe",
        datetime.combine(friday, datetime.min.time()) + timedelta(hours=16),
    )
    agenda.add(
        "reunião com fornecedor",
        datetime.combine(friday, datetime.min.time()) + timedelta(days=7, hours=10),
    )
    message = handle("cancela a reunião de sexta").message
    assert message.startswith("Desmarquei reunião de equipe")
    assert [e.title for e in agenda.upcoming(days=30)] == ["reunião com fornecedor"]


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------


def test_ics_has_events_and_alarm():
    timed = agenda.add("reunião; com, vírgula", _next_weekday_at(10))
    all_day = agenda.add(
        "feriado",
        datetime.combine(date.today() + timedelta(days=3), datetime.min.time()),
        all_day=True,
    )
    ics = agenda.to_ics([timed, all_day])
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 2
    assert "SUMMARY:reunião\\; com\\, vírgula" in ics
    assert "TRIGGER:-PT15M" in ics
    assert f"DTSTART;VALUE=DATE:{all_day.start_at:%Y%m%d}" in ics


def test_export_outside_windows_saves_the_file(monkeypatch):
    agenda.add("reunião", _next_weekday_at(10))
    monkeypatch.setattr(executores.sys, "platform", "linux")
    message = handle("manda pro calendário").message
    assert message.startswith("Salvei 1 compromisso em")
    assert message.split(" em ", 1)[1].split(".ics")[0].endswith(tuple("0123456789"))


# ---------------------------------------------------------------------------
# Ferramenta do modelo
# ---------------------------------------------------------------------------


def test_agenda_tool():
    from nicx.acoes.ferramenta import AgendaTool

    tool = AgendaTool()
    ok = tool.execute(
        acao="marcar", titulo="dentista", quando="depois de amanhã às 10h"
    )
    assert ok.success and "Marquei dentista" in ok.content
    seen = tool.execute(acao="ver", quando="depois de amanhã")
    assert "dentista às 10h" in seen.content
    bad = tool.execute(acao="marcar", titulo="algo", quando="quando der")
    assert not bad.success
    gone = tool.execute(acao="desmarcar", titulo="dentista")
    assert gone.success and agenda.upcoming(days=7) == []
