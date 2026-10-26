"""Supabase delivery: batching, headers, failure handling, and the routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.nucleo.config import NicxConfig
from nicx.privacidade import POLICY_VERSION, supabase_sink
from nicx.privacidade.supabase_sink import SupabaseSink, forget_installation
from nicx.servidor.rotas import privacidade as analytics_routes

URL = "https://example.supabase.co"
PUBLISHABLE = "sb_publishable_test"


@pytest.fixture
def posted(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        response = MagicMock(status_code=201, text="")
        response.json.return_value = 3
        return response

    monkeypatch.setattr(supabase_sink.httpx, "post", fake_post)
    return calls


def _sink(**kwargs) -> SupabaseSink:
    return SupabaseSink(URL, PUBLISHABLE, flush_interval=3600, **kwargs)


def test_flush_posts_batched_rows_to_events_table(posted) -> None:
    sink = _sink(context={"app_version": "1.2.3", "os": "windows", "arch": "x86_64"})
    sink.capture("anon-1", "app_opened", {"platform": "tauri-windows"})
    sink.capture("anon-1", "feature_used", {"feature_name": "voice"})
    sink.flush()
    sink.shutdown()

    assert len(posted) == 1
    call = posted[0]
    assert call["url"] == f"{URL}/rest/v1/nicx_events"
    assert call["headers"]["apikey"] == PUBLISHABLE
    assert call["headers"]["Prefer"] == "return=minimal"
    assert "Authorization" not in call["headers"]
    rows = call["json"]
    assert [row["event"] for row in rows] == ["app_opened", "feature_used"]
    assert rows[0]["platform"] == "tauri-windows"
    assert rows[1]["platform"] == "cli"
    assert rows[0]["app_version"] == "1.2.3"
    assert rows[0]["anon_id"] == "anon-1"
    assert rows[0]["sent_at"]


def test_legacy_anon_jwt_also_sends_bearer_header(posted) -> None:
    sink = SupabaseSink(URL, "eyJhbGciOi.legacy", flush_interval=3600)
    sink.capture("anon-1", "app_opened", {})
    sink.shutdown()
    assert posted[0]["headers"]["Authorization"] == "Bearer eyJhbGciOi.legacy"


def test_network_failure_is_swallowed(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(supabase_sink.httpx, "post", boom)
    sink = _sink()
    sink.capture("anon-1", "app_opened", {})
    sink.flush()
    sink.shutdown()


def test_reaching_flush_at_wakes_the_sender(posted) -> None:
    sink = _sink(flush_at=2)
    sink.capture("anon-1", "app_opened", {})
    sink.capture("anon-1", "app_opened", {})
    sink._thread.join(timeout=0.05)
    sink.shutdown()
    assert sum(len(call["json"]) for call in posted) == 2


def test_capture_after_shutdown_is_ignored(posted) -> None:
    sink = _sink()
    sink.shutdown()
    sink.capture("anon-1", "app_opened", {})
    sink.flush()
    assert posted == []


def test_forget_installation_calls_the_rpc(posted) -> None:
    assert forget_installation(URL, PUBLISHABLE, "anon-1") == 3
    assert posted[0]["url"] == f"{URL}/rest/v1/rpc/nicx_forget"
    assert posted[0]["json"] == {"p_anon_id": "anon-1"}


# -- Routes -------------------------------------------------------------------


@pytest.fixture
def app_with_client(tmp_path: Path):
    cfg = NicxConfig()
    cfg.analytics.host = URL
    cfg.analytics.key = PUBLISHABLE
    cfg.analytics.anon_id_path = str(tmp_path / "anon_id")
    app = FastAPI()
    app.state.config = cfg
    app.include_router(analytics_routes.router)
    return app, cfg


def test_capture_route_forwards_only_with_consent(app_with_client) -> None:
    app, _ = app_with_client
    http = TestClient(app)
    payload = {"event": "feature_used", "properties": {"feature_name": "voice"}}

    assert http.post("/v1/analytics/capture", json=payload).status_code == 204

    client = MagicMock(enabled=True)
    app.state.analytics_client = client
    assert http.post("/v1/analytics/capture", json=payload).status_code == 204
    client.capture.assert_called_once_with("feature_used", {"feature_name": "voice"})


def test_capture_route_rejects_unknown_fields(app_with_client) -> None:
    app, _ = app_with_client
    response = TestClient(app).post(
        "/v1/analytics/capture", json={"event": "x", "content": "secret"}
    )
    assert response.status_code == 422


def test_forget_route_erases_remotely_and_rotates_id(app_with_client, monkeypatch):
    app, cfg = app_with_client
    Path(cfg.analytics.anon_id_path).write_text("old-id\n", encoding="utf-8")
    seen = {}

    def fake_forget(url, key, anon_id):
        seen.update(url=url, key=key, anon_id=anon_id)
        return 7

    monkeypatch.setattr(analytics_routes, "forget_installation", fake_forget)
    response = TestClient(app).post("/v1/analytics/forget")

    assert response.status_code == 200
    body = response.json()
    assert body["removed"] == 7
    assert seen == {"url": URL, "key": PUBLISHABLE, "anon_id": "old-id"}
    assert body["anon_id"] != "old-id"
    assert (
        Path(cfg.analytics.anon_id_path).read_text(encoding="utf-8").strip()
        == (body["anon_id"])
    )


def test_forget_route_reports_remote_failure(app_with_client, monkeypatch):
    app, cfg = app_with_client
    Path(cfg.analytics.anon_id_path).write_text("old-id\n", encoding="utf-8")

    def failing(*args):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(analytics_routes, "forget_installation", failing)
    response = TestClient(app).post("/v1/analytics/forget")
    assert response.status_code == 502
    # The local ID is kept so the user can retry the erasure.
    assert Path(cfg.analytics.anon_id_path).read_text(encoding="utf-8").strip() == (
        "old-id"
    )


def test_dashboard_config_exposes_public_settings(app_with_client) -> None:
    app, _ = app_with_client
    body = TestClient(app).get("/v1/analytics/dashboard-config").json()
    assert body == {
        "supabase_url": URL,
        "supabase_key": PUBLISHABLE,
        "policy_version": POLICY_VERSION,
    }
