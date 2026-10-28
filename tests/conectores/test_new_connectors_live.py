"""Live smoke tests for new connectors — require real API credentials.

Run with: uv run pytest tests/conectores/test_new_connectors_live.py -v -m cloud

Sem o token do serviço (conector não conectado), cada teste é pulado.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from nicx.conectores._stubs import BaseConnector, Document


def _require_connected(conn: BaseConnector, service: str) -> None:
    if not conn.is_connected():
        pytest.skip(f"{service} não está conectado: falta o token da conta real")


@pytest.mark.cloud
class TestOuraLive:
    def test_sync_returns_documents(self):
        from nicx.conectores.oura import OuraConnector

        conn = OuraConnector()  # Uses default token path
        _require_connected(conn, "Oura")
        docs = list(conn.sync(since=datetime.now() - timedelta(days=1)))
        assert len(docs) > 0
        assert all(isinstance(d, Document) for d in docs)
        assert all(d.source == "oura" for d in docs)


@pytest.mark.cloud
class TestStravaLive:
    def test_sync_returns_documents(self):
        from nicx.conectores.strava import StravaConnector

        conn = StravaConnector()
        _require_connected(conn, "Strava")
        docs = list(conn.sync(since=datetime.now() - timedelta(days=7)))
        assert all(isinstance(d, Document) for d in docs)
        assert all(d.source == "strava" for d in docs)


@pytest.mark.cloud
class TestSpotifyLive:
    def test_sync_returns_documents(self):
        from nicx.conectores.spotify import SpotifyConnector

        conn = SpotifyConnector()
        _require_connected(conn, "Spotify")
        docs = list(conn.sync(since=datetime.now() - timedelta(days=1)))
        assert all(isinstance(d, Document) for d in docs)
        assert all(d.source == "spotify" for d in docs)


@pytest.mark.cloud
class TestGoogleTasksLive:
    def test_sync_returns_documents(self):
        from nicx.conectores.google_tasks import GoogleTasksConnector

        conn = GoogleTasksConnector()
        _require_connected(conn, "Google Tasks")
        docs = list(conn.sync(since=datetime.now() - timedelta(days=7)))
        assert all(isinstance(d, Document) for d in docs)
        assert all(d.source == "google_tasks" for d in docs)
