"""Logs de aviso e erro e saúde do servidor para o painel (com consentimento)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from nicx.privacidade import logs
from nicx.privacidade.events import known_event_names, validate_event
from nicx.privacidade.saude import model_family, server_started_properties

# ---------------------------------------------------------------------------
# Limpeza da mensagem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Falha ao ler 'meu currículo.pdf'", "Falha ao ler …"),
        ('Prompt "me lembra de ligar pra mãe" falhou', "Prompt … falhou"),
        ("Sem acesso a C:\\Users\\Arthur\\Documentos\\x.txt", "Sem acesso a <caminho>"),
        ("Arquivo /home/ana/notas.md sumiu", "Arquivo <caminho> sumiu"),
        ("Falhou (C:\\Users\\Ana\\x.txt), de novo", "Falhou (<caminho>), de novo"),
        ("Mande para ana@exemplo.com", "Mande para <email>"),
        ("Erro em https://site.com/a?b=c", "Erro em <link>"),
        ("Conexão 192.168.0.10:8000 caiu", "Conexão <ip> caiu"),
        ("token abcdefghijklmnopqrstuvwxyzABCDEF12 vazou", "token <token> vazou"),
        ("pedido 1234567 falhou", "pedido <n> falhou"),
        ("Ollama   não\nrespondeu", "Ollama não respondeu"),
    ],
)
def test_sanitize_removes_personal_data(raw, expected):
    assert logs.sanitize(raw) == expected


def test_sanitize_caps_length():
    assert len(logs.sanitize("x " * 400)) <= logs.MAX_MESSAGE


def _record(msg, *args, name="nicx.teste", level=logging.WARNING, exc=None):
    exc_info = (type(exc), exc, exc.__traceback__) if exc is not None else None
    return logging.LogRecord(name, level, __file__, 10, msg, args, exc_info)


# ---------------------------------------------------------------------------
# Agrupamento e envio
# ---------------------------------------------------------------------------


@pytest.fixture
def shipper(monkeypatch):
    sent: list[list[dict]] = []

    class _Response:
        status_code = 201
        text = ""

    def fake_post(url, json, headers, timeout):  # noqa: A002
        sent.append(json)
        return _Response()

    monkeypatch.setattr(logs.httpx, "post", fake_post)
    handler = logs.LogShipper(
        "https://exemplo.supabase.co",
        "sb_publishable_teste",
        "00000000-0000-4000-8000-000000000001",
        context={"app_version": "1.0.0", "os": "windows", "arch": "x86_64"},
        flush_interval=3600,
    )
    yield handler, sent
    handler.close()


def test_same_warning_is_grouped_with_count(shipper):
    handler, sent = shipper
    for attempt in range(3):
        handler.handle(_record("Motor %r fora do ar (tentativa %d)", "ollama", attempt))
    handler.flush()
    assert len(sent) == 1 and len(sent[0]) == 1
    row = sent[0][0]
    assert row["occurrences"] == 3
    assert row["level"] == "warning"
    assert row["message"] == "Motor … fora do ar (tentativa 0)"
    assert re.fullmatch(r"[0-9a-f]{16}", row["fingerprint"])
    assert row["anon_id"].endswith("0001") and row["app_version"] == "1.0.0"


def test_exception_sends_type_and_code_location_only(shipper):
    handler, sent = shipper
    try:
        raise ValueError("segredo do usuário: senha123")
    except ValueError as exc:
        handler.handle(
            _record("Falhou", name="nicx.motores.teste", level=logging.ERROR, exc=exc)
        )
    handler.flush()
    row = sent[0][0]
    assert row["exc_type"] == "ValueError"
    assert "senha123" not in str(row)
    assert row["location"].startswith("nicx.motores.teste:")


def test_noise_and_own_logs_are_ignored(shipper):
    handler, sent = shipper
    handler.handle(_record("ok", level=logging.INFO))
    handler.handle(_record("lote recusado", name="nicx.privacidade.logs"))
    handler.handle(
        _record(
            "conexão", name="asyncio", level=logging.ERROR, exc=ConnectionResetError()
        )
    )
    handler.flush()
    assert sent == []


def test_pii_left_after_cleanup_falls_back_to_template(shipper):
    handler, sent = shipper
    # Um IPv6 escapa da limpeza, mas a checagem final pega e manda só o modelo.
    handler.handle(_record("Servidor %s recusou", "fe80::1:2:3"))
    handler.flush()
    assert sent[0][0]["message"] == "Servidor %s recusou"


def test_install_and_uninstall_attach_to_root(shipper):
    handler, _sent = shipper
    root = logging.getLogger()
    logs.install(handler)
    try:
        assert handler in root.handlers
        assert handler in logging.getLogger("uvicorn.error").handlers
    finally:
        logs.uninstall(handler)
    assert handler not in root.handlers


# ---------------------------------------------------------------------------
# Saúde do servidor
# ---------------------------------------------------------------------------


def test_model_family_keeps_only_public_looking_names():
    assert model_family("qwen3.5:4b") == "qwen3.5"
    assert model_family("library/llama3.2:3b") == "llama3.2"
    assert model_family("Modelo do João") is None


def test_server_started_event_passes_the_catalog():
    props = server_started_properties(
        engine="ollama",
        model="qwen3.5:4b",
        engine_autostarted=True,
        voice_input=True,
        voice_output=True,
        wake_word=False,
        quick_actions=True,
        startup_ms=8123,
    )
    cleaned = validate_event("server_started", props)
    assert cleaned is not None
    assert (
        cleaned["model_family"] == "qwen3.5" and cleaned["engine_autostarted"] is True
    )
    assert validate_event(
        "server_health",
        {"rss_mb": 300, "ram_percent": 54, "cpu_percent": 7, "uptime_min": 61},
    )


def test_every_catalog_event_is_allowed_by_the_database():
    """Evento novo no catálogo sem entrar no check do banco seria recusado calado."""
    migrations = sorted(Path("supabase/migrations").glob("*.sql"))
    latest = next(
        m.read_text(encoding="utf-8")
        for m in reversed(migrations)
        if "nicx_events_event_check" in m.read_text(encoding="utf-8")
        or "event in (" in m.read_text(encoding="utf-8")
    )
    allowed = set(
        re.findall(r"'([a-z_]+)'", latest.split("event in (", 1)[1].split(")", 1)[0])
    )
    assert set(known_event_names()) <= allowed


# ---------------------------------------------------------------------------
# Ollama ligado pelo Nicx desliga junto
# ---------------------------------------------------------------------------


def test_stop_started_server_only_touches_what_nicx_started(monkeypatch):
    from nicx.motores import ollama

    monkeypatch.setattr(ollama, "_started", None)
    ollama.stop_started_server()  # nada ligado: não faz nada
    assert not ollama.started_by_nicx()

    calls: list[str] = []

    class FakeProcess:
        pid = 4321

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout):
            calls.append("wait")

    monkeypatch.setattr(ollama, "_started", FakeProcess())
    # Fora do Windows o processo recebe terminate(); no Windows, taskkill /T.
    monkeypatch.setattr("sys.platform", "linux")
    assert ollama.started_by_nicx()
    ollama.stop_started_server()
    assert calls == ["terminate", "wait"]
    assert not ollama.started_by_nicx()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.0.0.0", "http://127.0.0.1:11434"),
        ("127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("0.0.0.0:12000", "http://127.0.0.1:12000"),
        ("http://localhost:11434/", "http://localhost:11434"),
        ("https://ollama.exemplo.com", "https://ollama.exemplo.com"),
    ],
)
def test_ollama_host_in_ollama_format(raw, expected):
    from nicx.motores.ollama import _normalize_host

    assert _normalize_host(raw) == expected
