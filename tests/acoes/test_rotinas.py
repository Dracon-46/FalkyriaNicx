"""Rotinas: lembretes, anotações, estado do PC, pastas, print, fechar apps, energia."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from nicx.acoes import confirmacao, executores, handle, lembretes, notas, parse
from nicx.acoes.tempo import parse_when, say_when

NOW = datetime(2026, 10, 27, 14, 10)


@pytest.fixture(autouse=True)
def nicx_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"
    confirmacao.drop()


# ---------------------------------------------------------------------------
# Horários
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("em 10 minutos", NOW + timedelta(minutes=10)),
        ("em vinte e cinco minutos", NOW + timedelta(minutes=25)),
        ("daqui a meia hora", NOW + timedelta(minutes=30)),
        ("em uma hora e meia", NOW + timedelta(minutes=90)),
        ("em 2 horas e 15 minutos", NOW + timedelta(minutes=135)),
        ("as 15h30", datetime(2026, 10, 27, 15, 30)),
        ("as 3 da tarde", datetime(2026, 10, 27, 15, 0)),
        ("as 8", datetime(2026, 10, 27, 20, 0)),  # 8h já passou: 20h
        ("amanha as 8", datetime(2026, 10, 28, 8, 0)),
        ("as 7 da manha", datetime(2026, 10, 28, 7, 0)),
        ("as 22:45", datetime(2026, 10, 27, 22, 45)),
        ("as 9 e meia", datetime(2026, 10, 27, 21, 30)),
        ("as 12 da noite", datetime(2026, 10, 28, 0, 0)),
        ("amanha as 3", datetime(2026, 10, 28, 15, 0)),
        ("as 3", datetime(2026, 10, 27, 15, 0)),
        ("as 25h", None),
        ("em banana", None),
    ],
)
def test_parse_when(text, expected):
    assert parse_when(text, NOW) == expected


def test_say_when():
    assert say_when(NOW + timedelta(minutes=20), NOW) == "em 20 minutos"
    assert say_when(datetime(2026, 10, 27, 15, 30), NOW) == "às 15h30"
    assert say_when(datetime(2026, 10, 28, 8, 0), NOW) == "amanhã às 8h"


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "target"),
    [
        (
            "Me lembra de tirar o bolo do forno em 20 minutos",
            "remind",
            "tirar o bolo do forno",
        ),
        ("Nicx, me lembra amanhã às 8 de pagar a conta", "remind", "pagar a conta"),
        ("daqui a meia hora me lembra de ligar pra mãe", "remind", "ligar pra mãe"),
        (
            "me avisa às 3 da tarde que tenho reunião com o João",
            "remind",
            "tenho reunião com o João",
        ),
        ("timer de 5 minutos", "remind", "o tempo acabou"),
        ("coloca um alarme para as 7 da manhã", "remind", "alarme"),
        ("quais são meus lembretes", "remind_list", ""),
        ("cancela os lembretes", "remind_clear", ""),
        ("Anota aí: comprar pão e café", "note_add", "comprar pão e café"),
        ("lê minhas anotações", "notes_list", ""),
        ("como tá o computador?", "status", ""),
        ("abre a pasta downloads", "folder", "downloads"),
        ("abre meus documentos", "folder", "documentos"),
        ("tira um print", "screenshot", ""),
        ("fecha o Chrome", "close", "chrome"),
        ("desliga o computador", "power", ""),
    ],
)
def test_parse_routines(text, kind, target):
    action = parse(text)
    assert action is not None and action.kind == kind
    assert action.target == target


@pytest.mark.parametrize(
    "text",
    [
        "me lembra de algo",
        "Como faço um lembrete no celular?",
        "fecha a porta",
        "quero que você anote isso em algum lugar",
        "sim",  # sem nada pendente, é conversa
        "Você pode anotar o que eu falar daqui pra frente?",
        "Consegue anotar uma coisa pra mim?",
        "Anotar à mão ajuda a memorizar?",
        "Me lembra as 3 leis de Newton",
        "Me lembra disso amanhã às 9",
    ],
)
def test_parse_leaves_conversation_alone(text):
    assert parse(text) is None


# ---------------------------------------------------------------------------
# Lembretes
# ---------------------------------------------------------------------------


def test_reminders_are_saved_listed_and_cleared(nicx_home):
    assert handle("me lembra de beber água em 10 minutos").ok
    assert handle("timer de 5 minutos").message == "Timer marcado: aviso em 5 minutos."
    listed = handle("quais meus lembretes").message
    assert listed.startswith("Você tem 2 lembretes: timer em")
    assert "beber água" in listed
    assert (nicx_home / "lembretes.json").exists()
    assert handle("cancela os lembretes").message == "Cancelei 2 lembretes."
    assert handle("quais meus lembretes").message == "Você não tem lembretes marcados."


def test_pop_due_only_returns_what_is_due():
    lembretes.add("antes", NOW - timedelta(minutes=1))
    lembretes.add("depois", NOW + timedelta(hours=1))
    assert [r.text for r in lembretes.pop_due(NOW)] == ["antes"]
    assert [r.text for r in lembretes.pending()] == ["depois"]


def test_late_reminder_says_it_was_late():
    reminder = lembretes.add("pagar a conta", NOW - timedelta(minutes=30))
    assert "o Nicx estava desligado" in lembretes.message_for(reminder, NOW)
    on_time = lembretes.add("beber água", NOW)
    assert lembretes.message_for(on_time, NOW) == "Lembrete: beber água."


def test_alarm_fires_due_reminders():
    fired: list[str] = []
    done = threading.Event()

    def on_due(reminder):
        fired.append(reminder.text)
        done.set()

    lembretes.add("tirar o bolo", datetime.now() - timedelta(seconds=1))
    lembretes.stop_alarm()
    lembretes.start_alarm(interval=0.05, on_due=on_due)
    try:
        assert done.wait(5)
    finally:
        lembretes.stop_alarm()
    assert fired == ["tirar o bolo"]
    assert lembretes.pending() == []


# ---------------------------------------------------------------------------
# Anotações
# ---------------------------------------------------------------------------


def test_notes_are_kept_in_a_markdown_file(nicx_home):
    assert handle("anota: comprar pão").message == "Anotado."
    handle("anota que a reunião mudou para sexta")
    assert handle("lê minhas anotações").message == (
        "Suas últimas 2 anotações: comprar pão; a reunião mudou para sexta."
    )
    text = (nicx_home / "notas.md").read_text(encoding="utf-8")
    assert text.startswith("# Anotações do Nicx")
    assert notas.clear() == 2
    assert handle("lê minhas anotações").message == "Você ainda não tem anotações."


# ---------------------------------------------------------------------------
# Energia: sempre pede confirmação
# ---------------------------------------------------------------------------


@pytest.fixture
def commands(monkeypatch):
    ran: list[list[str]] = []
    monkeypatch.setattr(executores.sys, "platform", "win32")
    monkeypatch.setattr(
        executores.subprocess, "run", lambda cmd, **_kw: ran.append(list(cmd))
    )
    return ran


def test_shutdown_needs_confirmation(commands):
    assert "Tem certeza" in handle("desliga o computador").message
    assert commands == []
    assert handle("confirmo").message.startswith("Desligando em 30 segundos")
    assert commands == [["shutdown", "/s", "/t", "30"]]
    # Confirmação vale uma vez só.
    assert parse("confirmo") is None


def test_saying_no_cancels(commands):
    handle("reinicia o pc")
    assert handle("não").message == "Tudo bem, não vou fazer nada."
    assert commands == []


def test_confirmation_expires(commands, monkeypatch):
    handle("desliga o computador")
    monkeypatch.setattr(confirmacao, "WINDOW_SECONDS", -1)
    assert parse("confirmo") is None


def test_abort_shutdown_runs_right_away(commands):
    assert handle("cancela o desligamento").message == "Desligamento cancelado."
    assert commands == [["shutdown", "/a"]]


# ---------------------------------------------------------------------------
# Fechar apps, pastas, print, estado
# ---------------------------------------------------------------------------


def _procs(*names):
    return [SimpleNamespace(info={"name": n}) for n in names]


def test_close_app_asks_politely(commands, monkeypatch):
    import psutil

    monkeypatch.setattr(
        psutil, "process_iter", lambda *_a: _procs("chrome.exe", "x.exe")
    )
    assert handle("fecha o chrome").message == "Fechando o Chrome."
    assert commands == [["taskkill", "/IM", "chrome.exe"]]  # sem /F


def test_close_app_not_running(commands, monkeypatch):
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda *_a: _procs("explorer.exe"))
    assert handle("fecha o spotify").message == "O Spotify não está aberto."
    assert commands == []


def test_open_folder(monkeypatch, tmp_path):
    (tmp_path / "Downloads").mkdir()
    opened = []
    monkeypatch.setattr(executores.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(executores, "_start", opened.append)
    assert handle("abre a pasta downloads").message == "Abrindo Downloads."
    assert opened == [str(tmp_path / "Downloads")]
    assert handle("abre a pasta de vídeos").message == "Não achei a pasta Vídeos."


def test_screenshot_saves_in_pictures(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image, ImageGrab

    (tmp_path / "Pictures").mkdir()
    monkeypatch.setattr(executores.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(ImageGrab, "grab", lambda **_kw: Image.new("RGB", (4, 4)))
    assert handle("tira um print").message == "Print salvo em Pictures\\Nicx."
    assert len(list((tmp_path / "Pictures" / "Nicx").glob("print-*.png"))) == 1


def test_status_reports_cpu_memory_and_heavy_apps(monkeypatch):
    import psutil

    gb = 1024**3
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 12.0)
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(percent=85.0, available=2 * gb),
    )
    monkeypatch.setattr(psutil, "disk_usage", lambda _p: SimpleNamespace(free=70 * gb))
    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)
    procs = [
        SimpleNamespace(
            info={"name": "Code.exe", "memory_info": SimpleNamespace(rss=3 * gb)}
        ),
        SimpleNamespace(
            info={"name": "chrome.exe", "memory_info": SimpleNamespace(rss=gb)}
        ),
        SimpleNamespace(
            info={"name": "chrome.exe", "memory_info": SimpleNamespace(rss=gb)}
        ),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda *_a: procs)
    message = handle("como tá o pc?").message
    assert "processador em 12%" in message
    assert "memória 85% usada (2,0 GB livres)" in message
    assert "O que mais usa memória: Code (3,0 GB) e chrome (2,0 GB)." in message


# ---------------------------------------------------------------------------
# Ferramentas do modelo
# ---------------------------------------------------------------------------


def test_reminder_tool():
    from nicx.acoes.ferramenta import ReminderTool

    tool = ReminderTool()
    ok = tool.execute(quando="em 15 minutos", mensagem="dar comida pro gato")
    assert ok.success and "dar comida pro gato" in ok.content
    assert [r.text for r in lembretes.pending()] == ["dar comida pro gato"]
    bad = tool.execute(quando="quando der", mensagem="x")
    assert not bad.success and "horário" in bad.content


def test_computer_tool_new_actions(nicx_home):
    from nicx.acoes.ferramenta import ComputerControlTool

    tool = ComputerControlTool()
    assert tool.execute(acao="anotar", alvo="ligar pro banco").content == "Anotado."
    assert notas.all_notes() == ["ligar pro banco"]
    unknown = tool.execute(acao="abrir_pasta", alvo="segredos")
    assert not unknown.success and "downloads" in unknown.content
    # Desligar não está ao alcance do modelo.
    assert not tool.execute(acao="desligar").success


# ---------------------------------------------------------------------------
# Correções da revisão
# ---------------------------------------------------------------------------


def test_clock_with_colon_is_understood():
    action = parse("Me lembra às 15:30 de ligar pro banco")
    assert action is not None and action.kind == "remind"
    assert action.target == "ligar pro banco"
    assert (action.when.hour, action.when.minute) == (15, 30)


def test_three_oclock_after_three_is_tomorrow_afternoon():
    late = datetime(2026, 10, 27, 16, 0)
    assert parse_when("as 3", late) == datetime(2026, 10, 28, 15, 0)


def test_alarm_early_hours_stay_in_the_morning():
    action = parse("coloca um alarme para as 6")
    assert action is not None and action.when.hour == 6


def test_timer_near_midnight_is_said_in_minutes():
    now = datetime(2026, 10, 27, 23, 57)
    assert say_when(now + timedelta(minutes=5), now) == "em 5 minutos"


def test_cancel_the_timer_keeps_other_reminders():
    lembretes.add("pagar a conta", datetime.now() + timedelta(days=1))
    lembretes.add("o tempo acabou", datetime.now() + timedelta(minutes=10))
    message = handle("cancela o timer").message
    assert message.startswith("Cancelei o timer de")
    assert [r.text for r in lembretes.pending()] == ["pagar a conta"]
    assert handle("cancela os alarmes").message == "Não havia alarmes para cancelar."
    assert handle("cancela os lembretes").message == "Cancelei 1 lembrete."
