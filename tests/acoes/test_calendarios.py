"""Agenda -> Google Agenda e Outlook: links preenchidos, API (simulada) e avisos
no idioma do pedido. Nada aqui acessa a rede."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from nicx.acoes import (
    agenda,
    calendarios,
    executores,
    handle,
    lembretes,
    parse,
)


@pytest.fixture(autouse=True)
def nicx_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("NICX_HOME", str(home))
    monkeypatch.setenv("NICX_CONFIG", str(home / "config.toml"))
    return home


@pytest.fixture(autouse=True)
def config(monkeypatch):
    cfg = SimpleNamespace(calendario_padrao="windows", fuso="America/Sao_Paulo")
    monkeypatch.setattr(calendarios, "_config_agenda", lambda: cfg)
    return cfg


@pytest.fixture(autouse=True)
def opened(monkeypatch):
    """O que seria aberto no navegador / no app padrão."""
    seen: list[str] = []
    monkeypatch.setattr(executores, "_start", seen.append)
    return seen


@pytest.fixture
def no_http(monkeypatch):
    """Falha se alguém tentar a API de verdade."""

    def boom(*_a, **_kw):
        raise AssertionError("chamada HTTP inesperada")

    from nicx.conectores import gcalendar, outlook

    monkeypatch.setattr(gcalendar, "_gcal_api_event_insert", boom)
    monkeypatch.setattr(outlook, "_graph_api_event_create", boom)


def _event(**kw) -> agenda.Event:
    base = dict(
        id="abc12345",
        title="Reunião & café",
        start="2026-10-30T15:00:00",
        all_day=False,
        created="2026-10-28T09:00:00",
    )
    base.update(kw)
    return agenda.Event(**base)


def _future(hour: int = 15, days: int = 2) -> datetime:
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def _connectors(home):
    folder = home / "connectors"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _google_tokens(home, scope=None, **extra):
    data = {"access_token": "tok", "refresh_token": "ref", **extra}
    if scope is not None:
        data["scope"] = scope
    (_connectors(home) / "gcalendar.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.invalid")
    return httpx.HTTPStatusError(
        "erro", request=request, response=httpx.Response(status, request=request)
    )


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def test_google_link_encodes_and_uses_timezone():
    url = calendarios.link_google(_event(details="pauta: 1/2", location="Sala 3"))
    assert url == (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        "&text=Reuni%C3%A3o%20%26%20caf%C3%A9"
        "&dates=20261030T150000/20261030T160000"
        "&details=pauta:%201/2&location=Sala%203&ctz=America/Sao_Paulo"
    )
    query = parse_qs(urlparse(url).query)
    assert query["text"] == ["Reunião & café"]


def test_google_link_all_day_has_no_time_and_exclusive_end():
    url = calendarios.link_google(_event(start="2026-10-31T00:00:00", all_day=True))
    assert parse_qs(urlparse(url).query)["dates"] == ["20261031/20261101"]


def test_google_link_keeps_saved_end():
    url = calendarios.link_google(_event(end="2026-10-30T17:30:00"))
    assert "dates=20261030T150000/20261030T173000" in url


def test_outlook_links_personal_and_work():
    personal = calendarios.link_outlook(_event())
    assert personal.startswith(
        "https://outlook.live.com/calendar/0/deeplink/compose?"
        "path=/calendar/action/compose&rru=addevent"
    )
    query = parse_qs(urlparse(personal).query)
    assert query["subject"] == ["Reunião & café"]
    assert query["startdt"] == ["2026-10-30T15:00:00-03:00"]
    assert query["enddt"] == ["2026-10-30T16:00:00-03:00"]  # 1 h por padrão
    assert query["allday"] == ["false"]
    assert "%20%26%20" in personal and "+" not in personal

    work = calendarios.link_outlook(_event(all_day=True), trabalho=True)
    assert work.startswith("https://outlook.office.com/calendar/0/deeplink/compose?")
    query = parse_qs(urlparse(work).query)
    assert (query["startdt"], query["enddt"], query["allday"]) == (
        ["2026-10-30"],
        ["2026-10-31"],
        ["true"],
    )


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "op", "target", "site"),
    [
        ("manda pro Google Agenda", "google", "", ""),
        ("manda pro Outlook", "outlook", "", ""),
        ("coloca isso no Outlook do trabalho", "outlook_trabalho", "", "ultimo"),
        ("manda pro calendário", "", "", ""),
        ("manda pro calendário do Windows", "windows", "", ""),
        (
            "manda a reunião de sexta pro Google Agenda",
            "google",
            "reuniao de sexta",
            "",
        ),
        ("passa meus compromissos pra agenda do Google", "google", "", "todos"),
        ("manda o dentista pro google calendar", "google", "dentista", ""),
    ],
)
def test_send_phrases(text, op, target, site):
    action = parse(text)
    assert action is not None and action.kind == "agenda_export"
    assert (action.op, action.target, action.site) == (op, target, site)


@pytest.mark.parametrize(
    ("idioma", "text", "op", "site"),
    [
        ("en", "send it to Google Calendar", "google", "ultimo"),
        ("en", "add everything to my work Outlook", "outlook_trabalho", "todos"),
        ("es", "mándalo a Google Calendar", "google", ""),
        ("es", "pasa todo al calendario de Outlook", "outlook", "todos"),
        ("fr", "envoie ça à Google Agenda", "google", "ultimo"),
        ("fr", "ajoute le rendez-vous à Outlook", "outlook", "ultimo"),
    ],
)
def test_send_phrases_other_languages(idioma, text, op, site):
    action = parse(text, idioma)
    assert action is not None and action.kind == "agenda_export"
    assert (action.op, action.site) == (op, site)


@pytest.mark.parametrize(
    "text", ["manda um e-mail pro Outlook", "abre o Outlook", "manda isso pro Google"]
)
def test_not_calendar_phrases(text):
    action = parse(text)
    assert action is None or action.kind != "agenda_export"


def test_add_and_send_in_one_phrase():
    action = parse("marca dentista sexta às 10h no Google Agenda")
    assert action.kind == "agenda_add" and action.target == "dentista"
    assert action.site == "google"
    action = parse("coloca reunião sexta às 15h no Outlook")
    assert action.kind == "agenda_add" and action.site == "outlook"


# ---------------------------------------------------------------------------
# Sem login: link preenchido
# ---------------------------------------------------------------------------


def test_send_last_added_opens_prefilled_link(opened, no_http):
    agenda.add("dentista", _future(10))
    agenda.add("reunião com o João", _future(15))
    message = handle("manda pro Google Agenda").message
    assert message == "Abri reunião com o João no Google Agenda: é só clicar em Salvar."
    assert len(opened) == 1 and opened[0].startswith(calendarios.GOOGLE_RENDER)
    assert "Jo%C3%A3o" in opened[0]


def test_send_cited_event(opened, no_http):
    friday = _future(16, days=3)
    agenda.add("reunião de equipe", friday)
    agenda.add("almoço", _future(12))
    day = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    text = f"manda a reunião de {day[friday.weekday()]} pro Outlook"
    assert handle(text).ok
    assert len(opened) == 1 and "subject=reuni%C3%A3o%20de%20equipe" in opened[0]
    assert opened[0].startswith(calendarios.OUTLOOK_PESSOAL)


def test_cited_event_not_found(opened):
    agenda.add("almoço", _future(12))
    outcome = handle("manda o dentista pro Google Agenda")
    assert not outcome.ok and "Não achei" in outcome.message
    assert opened == []


def test_default_calendar_decides_where_it_goes(config, opened, no_http, monkeypatch):
    agenda.add("reunião", _future(10))
    config.calendario_padrao = "outlook_trabalho"
    message = handle("manda pro calendário").message
    assert message.startswith("Abri reunião no Outlook")
    assert opened[0].startswith(calendarios.OUTLOOK_TRABALHO)
    # O padrão "windows" mantém o .ics de sempre.
    config.calendario_padrao = "windows"
    monkeypatch.setattr(executores.sys, "platform", "linux")
    assert handle("manda pro calendário").message.startswith("Salvei 1 compromisso")


def test_unknown_default_falls_back_to_windows(config):
    config.calendario_padrao = "banana"
    assert calendarios.calendario_padrao() == "windows"


def test_many_events_open_one_tab_each(opened, no_http):
    for hour in (9, 11, 14):
        agenda.add(f"evento {hour}", _future(hour))
    message = handle("manda meus compromissos pro Google Agenda").message
    assert message.startswith("Abri 3 compromissos no Google Agenda")
    assert len(opened) == 3


def test_answer_in_the_interface_language(opened, no_http):
    agenda.add("dentist", _future(10))
    message = handle("send it to Google Calendar", "en").message
    assert message == "I opened dentist in Google Calendar: just click Save."


def test_add_and_send_together(opened, no_http):
    day = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    when = _future(10, days=3)
    message = handle(
        f"marca dentista {day[when.weekday()]} às 10h no Google Agenda"
    ).message
    assert message.startswith("Marquei dentista")
    assert message.endswith("Abri dentista no Google Agenda: é só clicar em Salvar.")
    assert len(opened) == 1


# ---------------------------------------------------------------------------
# Google pela API (simulada)
# ---------------------------------------------------------------------------


def test_google_read_only_token_uses_link_and_asks_to_reconnect(
    nicx_home, opened, no_http
):
    _google_tokens(
        nicx_home, scope="openid https://www.googleapis.com/auth/calendar.readonly"
    )
    agenda.add("reunião", _future(10))
    message = handle("manda pro Google Agenda").message
    assert "Abri reunião no Google Agenda" in message
    assert "reconecte o Google Agenda dando permissão de escrita" in message
    assert len(opened) == 1


def test_google_write_token_creates_once(nicx_home, opened, monkeypatch):
    from nicx.conectores import gcalendar

    _google_tokens(
        nicx_home, scope="openid https://www.googleapis.com/auth/calendar.events"
    )
    calls = []

    def insert(token, calendar_id, body):
        calls.append((token, calendar_id, body))
        return {"id": body["id"], "htmlLink": "https://calendar.google.com/x"}

    monkeypatch.setattr(gcalendar, "_gcal_api_event_insert", insert)
    when = _future(15)
    event = agenda.add("reunião", when)
    assert handle("manda pro Google Agenda").message == (
        "Pronto: reunião já está no Google Agenda."
    )
    token, calendar_id, body = calls[0]
    assert (token, calendar_id) == ("tok", "primary")
    assert body["summary"] == "reunião"
    assert body["start"] == {
        "dateTime": when.isoformat(timespec="seconds"),
        "timeZone": "America/Sao_Paulo",
    }
    assert body["end"]["dateTime"] == (when + timedelta(hours=1)).isoformat()
    assert body["id"].startswith("nc" + event.id)
    assert set(body["id"]) <= set("0123456789abcdefghijklmnopqrstuv")
    assert agenda.get(event.id).google_id == body["id"]
    assert opened == []
    # De novo: não duplica.
    assert handle("manda pro Google Agenda").message == (
        "reunião já estava no Google Agenda."
    )
    assert len(calls) == 1


def test_google_all_day_body():
    body = calendarios.corpo_google(_event(start="2026-10-31T00:00:00", all_day=True))
    assert body["start"] == {"date": "2026-10-31"}
    assert body["end"] == {"date": "2026-11-01"}


def test_google_unknown_scope_403_falls_back(nicx_home, opened, monkeypatch):
    from nicx.conectores import gcalendar

    _google_tokens(nicx_home)  # conexão antiga: sem "scope" guardado

    def insert(*_a, **_kw):
        raise _http_error(403)

    monkeypatch.setattr(gcalendar, "_gcal_api_event_insert", insert)
    event = agenda.add("reunião", _future(10))
    message = handle("manda pro Google Agenda").message
    assert "Abri reunião" in message and "permissão de escrita" in message
    assert agenda.get(event.id).google_id == ""
    assert len(opened) == 1


def test_google_409_means_it_was_already_created(nicx_home, opened, monkeypatch):
    from nicx.conectores import gcalendar

    _google_tokens(nicx_home, scope="https://www.googleapis.com/auth/calendar")
    monkeypatch.setattr(
        gcalendar,
        "_gcal_api_event_insert",
        lambda *_a, **_kw: (_ for _ in ()).throw(_http_error(409)),
    )
    event = agenda.add("reunião", _future(10))
    assert handle("manda pro Google Agenda").message.startswith("Pronto")
    assert agenda.get(event.id).google_id.startswith("nc" + event.id)
    assert opened == []


def test_google_expired_token_is_refreshed(nicx_home, opened, monkeypatch):
    from nicx.conectores import gcalendar, google_auth

    _google_tokens(nicx_home, scope="https://www.googleapis.com/auth/calendar")
    tokens_used = []

    def insert(token, calendar_id, body):
        tokens_used.append(token)
        if token == "tok":
            raise _http_error(401)
        return {"id": "remote-1"}

    monkeypatch.setattr(gcalendar, "_gcal_api_event_insert", insert)
    monkeypatch.setattr(google_auth, "refresh_access_token", lambda _p: "novo")
    event = agenda.add("reunião", _future(10))
    assert handle("manda pro Google Agenda").message.startswith("Pronto")
    assert tokens_used == ["tok", "novo"]
    assert agenda.get(event.id).google_id == "remote-1"


def test_google_network_error_uses_link_without_reconnect(
    nicx_home, opened, monkeypatch
):
    from nicx.conectores import gcalendar

    _google_tokens(nicx_home, scope="https://www.googleapis.com/auth/calendar")

    def insert(*_a, **_kw):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(gcalendar, "_gcal_api_event_insert", insert)
    agenda.add("reunião", _future(10))
    message = handle("manda pro Google Agenda").message
    assert message == "Abri reunião no Google Agenda: é só clicar em Salvar."


def test_google_scope_now_asks_for_calendar_events():
    from nicx.conectores.oauth import GOOGLE_ALL_SCOPES

    assert "https://www.googleapis.com/auth/calendar.events" in GOOGLE_ALL_SCOPES
    # Quem já conectou com "calendar" continua podendo escrever.
    assert "https://www.googleapis.com/auth/calendar" in GOOGLE_ALL_SCOPES


# ---------------------------------------------------------------------------
# Outlook pelo Microsoft Graph (simulado)
# ---------------------------------------------------------------------------


def test_outlook_imap_only_uses_link(nicx_home, opened, no_http):
    (_connectors(nicx_home) / "outlook.json").write_text(
        json.dumps({"email_address": "a@b.com", "app_password": "x"}), encoding="utf-8"
    )
    agenda.add("reunião", _future(10))
    message = handle("manda pro Outlook").message
    assert message == "Abri reunião no Outlook: é só clicar em Salvar."
    assert opened[0].startswith(calendarios.OUTLOOK_PESSOAL)


def test_outlook_without_write_scope_asks_to_reconnect(nicx_home, opened, no_http):
    (_connectors(nicx_home) / "microsoft.json").write_text(
        json.dumps({"access_token": "ms", "scope": "Calendars.Read Mail.Read"}),
        encoding="utf-8",
    )
    agenda.add("reunião", _future(10))
    message = handle("manda pro Outlook").message
    assert "Abri reunião no Outlook" in message
    assert "permissão de agenda" in message


def test_outlook_graph_creates_once(nicx_home, opened, monkeypatch):
    from nicx.conectores import outlook

    (_connectors(nicx_home) / "microsoft.json").write_text(
        json.dumps(
            {
                "access_token": "ms",
                "scope": (
                    "https://graph.microsoft.com/Calendars.ReadWrite offline_access"
                ),
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def create(token, body):
        calls.append((token, body))
        return {"id": "AAMk-1"}

    monkeypatch.setattr(outlook, "_graph_api_event_create", create)
    when = _future(15)
    event = agenda.add("reunião", when)
    assert handle("manda pro Outlook do trabalho").message == (
        "Pronto: reunião já está no Outlook."
    )
    token, body = calls[0]
    assert token == "ms" and body["subject"] == "reunião"
    assert body["start"]["timeZone"] == "UTC" and body["isAllDay"] is False
    assert body["transactionId"].startswith(f"nicx-{event.id}")
    assert agenda.get(event.id).outlook_id == "AAMk-1"
    assert handle("manda pro Outlook").message == "reunião já estava no Outlook."
    assert len(calls) == 1
    assert opened == []


def test_outlook_graph_refreshes_expired_token(nicx_home, opened, monkeypatch):
    from nicx.conectores import outlook

    path = _connectors(nicx_home) / "microsoft.json"
    path.write_text(
        json.dumps(
            {
                "access_token": "velho",
                "refresh_token": "r",
                "client_id": "cid",
                "scope": "Calendars.ReadWrite offline_access",
            }
        ),
        encoding="utf-8",
    )
    used = []

    def create(token, body):
        used.append(token)
        if token == "velho":
            raise _http_error(401)
        return {"id": "AAMk-2"}

    posts = []

    def fake_post(url, data=None, timeout=None):
        posts.append((url, data))
        return httpx.Response(200, json={"access_token": "novo", "refresh_token": "r2"})

    monkeypatch.setattr(outlook, "_graph_api_event_create", create)
    monkeypatch.setattr(httpx, "post", fake_post)
    event = agenda.add("reunião", _future(10))
    assert handle("manda pro Outlook").message.startswith("Pronto")
    assert used == ["velho", "novo"]
    assert posts[0][0].startswith("https://login.microsoftonline.com/common/")
    assert posts[0][1]["client_id"] == "cid"
    assert json.loads(path.read_text(encoding="utf-8"))["access_token"] == "novo"
    assert agenda.get(event.id).outlook_id == "AAMk-2"


def test_outlook_all_day_body():
    body = calendarios.corpo_outlook(_event(start="2026-10-31T00:00:00", all_day=True))
    assert body["isAllDay"] is True
    assert body["start"]["dateTime"] == "2026-10-31T00:00:00"
    assert body["end"]["dateTime"] == "2026-11-01T00:00:00"


def test_outlook_timed_body_in_utc():
    body = calendarios.corpo_outlook(_event())
    assert body["start"] == {"dateTime": "2026-10-30T18:00:00", "timeZone": "UTC"}
    assert body["end"] == {"dateTime": "2026-10-30T19:00:00", "timeZone": "UTC"}


# ---------------------------------------------------------------------------
# Lembretes e avisos no idioma do pedido
# ---------------------------------------------------------------------------


def test_reminder_keeps_the_request_language():
    handle("remind me to drink water in 10 minutes", "en")
    (reminder,) = lembretes.pending()
    assert reminder.idioma == "en"
    assert lembretes.message_for(reminder, reminder.due_at) == "Reminder: drink water."


def test_timer_warning_in_spanish():
    handle("pon un temporizador de 5 minutos", "es")
    (reminder,) = lembretes.pending()
    assert lembretes.message_for(reminder, reminder.due_at) == (
        "Recordatorio: se acabó el tiempo."
    )


def test_appointment_warning_in_the_request_language():
    from nicx.acoes import textos

    with textos.usando("fr"):
        event = agenda.add("dentiste", _future(10))
    assert event.idioma == "fr"
    (reminder,) = lembretes.pending()
    assert reminder.text == "Dans 15 minutes : dentiste"
    late = reminder.due_at + timedelta(minutes=30)
    assert lembretes.message_for(reminder, late) == (
        "Rappel : Dans 15 minutes : dentiste. (c'était prévu à"
        f" {reminder.due_at:%H:%M} ; Nicx était éteint)"
    )


def test_old_files_without_language_still_work(nicx_home):
    nicx_home.mkdir(parents=True, exist_ok=True)
    due = datetime(2026, 10, 30, 9, 0)
    (nicx_home / "lembretes.json").write_text(
        json.dumps(
            [{"id": "a1", "text": "beber água", "due": due.isoformat(), "created": ""}]
        ),
        encoding="utf-8",
    )
    (nicx_home / "agenda.json").write_text(
        json.dumps(
            [
                {
                    "id": "e1",
                    "title": "velho",
                    "start": "2026-10-30T10:00:00",
                    "all_day": False,
                    "created": "2026-10-28T09:00:00",
                    "reminder_id": "",
                }
            ]
        ),
        encoding="utf-8",
    )
    (reminder,) = lembretes.pending()
    assert reminder.idioma == ""
    assert lembretes.message_for(reminder, due) == "Lembrete: beber água."
    (event,) = agenda.on_day(date(2026, 10, 30))
    assert (event.google_id, event.outlook_id, event.end) == ("", "", "")


# ---------------------------------------------------------------------------
# Leitura: eventos já sincronizados pelos conectores
# ---------------------------------------------------------------------------


def test_day_list_includes_synced_google_events(nicx_home):
    from nicx.conectores.store import KnowledgeStore

    when = _future(9)
    agenda.add("dentista", when.replace(hour=14))
    nicx_home.mkdir(parents=True, exist_ok=True)
    with KnowledgeStore(nicx_home / "knowledge.db") as store:
        aware = when.astimezone()
        store.store(
            f"Title: Daily\nWhen: {aware.isoformat()} – {aware.isoformat()}",
            source="gcalendar",
            doc_type="event",
            doc_id="gcalendar:x1",
            title="Daily",
            timestamp=aware,
            metadata={"event_id": "x1"},
        )
        day = when.date()
        store.store(
            f"Title: Feriado\nWhen: {day.isoformat()} – {day + timedelta(days=1)}",
            source="gcalendar",
            doc_type="event",
            doc_id="gcalendar:x2",
            title="Feriado",
            timestamp=datetime.combine(day, datetime.min.time()),
            metadata={"event_id": "x2"},
        )
    found = calendarios.eventos_conectados(when.date())
    assert [(e.title, e.all_day, e.origem) for e in found] == [
        ("Feriado", True, "google"),
        ("Daily", False, "google"),
    ]
    from nicx.acoes.intencoes import Action

    message = executores.agenda_list(
        Action(
            "agenda_list",
            op="dia",
            when=datetime.combine(when.date(), datetime.min.time()),
        )
    ).message
    assert "Feriado o dia todo (Google Agenda)" in message
    assert "Daily às 9h (Google Agenda)" in message
    assert message.index("Daily") < message.index("dentista")


def test_day_list_without_database_is_only_local(nicx_home):
    when = _future(10)
    agenda.add("dentista", when)
    assert calendarios.eventos_conectados(when.date()) == []


# ---------------------------------------------------------------------------
# Ferramenta do modelo e config
# ---------------------------------------------------------------------------


def test_agenda_tool_sends_to_google(opened, no_http):
    from nicx.acoes.ferramenta import AgendaTool

    agenda.add("dentista", _future(10))
    agenda.add("almoço", _future(12))
    result = AgendaTool().execute(acao="mandar_google", titulo="dentista")
    assert result.success and "Abri dentista no Google Agenda" in result.content
    result = AgendaTool().execute(acao="mandar_outlook")
    assert result.success and "Abri almoço no Outlook" in result.content


def test_save_default_writes_config(nicx_home, config):
    nicx_home.mkdir(parents=True, exist_ok=True)
    path = nicx_home / "config.toml"
    path.write_text('[engine]\ndefault = "ollama"\n', encoding="utf-8")
    calendarios.salvar_padrao("google")
    text = path.read_text(encoding="utf-8")
    assert 'default = "ollama"' in text and 'calendario_padrao = "google"' in text
    assert config.calendario_padrao == "google"
    with pytest.raises(ValueError):
        calendarios.salvar_padrao("yahoo")


def test_config_section():
    from nicx.nucleo.config import AgendaConfig, NicxConfig, validate_config_key

    assert AgendaConfig().calendario_padrao == "windows"
    assert NicxConfig().agenda.fuso == "America/Sao_Paulo"
    assert validate_config_key("agenda.calendario_padrao") is str
