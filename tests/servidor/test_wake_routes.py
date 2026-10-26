"""Rotas /v1/speech/wake: sinal de ocupado e ligar/desligar a escuta."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.nucleo.config import NicxConfig
from nicx.servidor.rotas import escuta as wake_routes
from nicx.servidor.rotas.escuta import WakeBusy


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_busy_expires_and_clears() -> None:
    clock = FakeClock()
    busy = WakeBusy(clock=clock)
    assert not busy.busy()
    busy.set("aba", True, ttl=10)
    assert busy.busy()
    clock.now = 9.9
    assert busy.busy()
    clock.now = 10.1
    assert not busy.busy()  # aba fechada sem avisar não trava a escuta
    busy.set("aba", True, ttl=10)
    busy.set("mascote", True, ttl=10)
    busy.set("aba", False)
    assert busy.busy()
    busy.set("mascote", False)
    assert not busy.busy()


def test_busy_ttl_is_capped() -> None:
    clock = FakeClock()
    busy = WakeBusy(clock=clock)
    busy.set("aba", True, ttl=10_000)
    clock.now = 31
    assert not busy.busy()


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Troca o lado de sistema (processos, atalho, config.toml) por registros."""
    from nicx.voz.escuta import runtime as rt

    calls: dict = {"enabled": [], "started": 0, "stopped": 0, "autostart": []}
    state: dict = {"running": None}

    def start_listener_process(*, only_if_enabled: bool = True) -> int:
        calls["started"] += 1
        state["running"] = {"pid": 4321, "state": "escutando"}
        return 4321

    def stop_listener(timeout: float = 4.0) -> bool:
        calls["stopped"] += 1
        state["running"] = None
        return True

    monkeypatch.setattr(rt, "set_wake_enabled", calls["enabled"].append)
    monkeypatch.setattr(rt, "start_listener_process", start_listener_process)
    monkeypatch.setattr(rt, "stop_listener", stop_listener)
    monkeypatch.setattr(rt, "read_state", lambda: state["running"])
    monkeypatch.setattr(
        rt, "autostart_enabled", lambda: bool(calls["autostart"][-1:] == [True])
    )
    monkeypatch.setattr(rt, "startup_dir", lambda: object())
    monkeypatch.setattr(rt, "window_supported", lambda: True)

    def set_autostart(enabled: bool) -> bool:
        calls["autostart"].append(enabled)
        return True

    monkeypatch.setattr(rt, "set_autostart", set_autostart)
    return calls


@pytest.fixture
def client(runtime: dict) -> TestClient:
    app = FastAPI()
    app.state.config = NicxConfig()
    app.include_router(wake_routes.router)
    return TestClient(app)


def test_status_defaults_to_off(client: TestClient) -> None:
    body = client.get("/v1/speech/wake").json()
    assert body["enabled"] is False
    assert body["running"] is False
    assert body["state"] == "parado"
    assert "Nicx, ligar" in body["phrases"]
    assert body["busy"] is False


def test_enable_and_disable(client: TestClient, runtime: dict) -> None:
    body = client.put("/v1/speech/wake", json={"enabled": True}).json()
    assert runtime["enabled"] == [True]
    assert runtime["started"] == 1
    assert body["enabled"] is True and body["running"] is True
    assert client.app.state.config.speech.wake_word is True

    body = client.put("/v1/speech/wake", json={"enabled": False}).json()
    assert runtime["enabled"] == [True, False]
    assert runtime["stopped"] == 1
    assert body["enabled"] is False and body["running"] is False


def test_autostart_toggle(client: TestClient, runtime: dict) -> None:
    body = client.put("/v1/speech/wake", json={"autostart": True}).json()
    assert runtime["autostart"] == [True]
    assert body["autostart"] is True
    assert runtime["started"] == 0  # só o atalho; a escuta não muda


def test_busy_round_trip(client: TestClient) -> None:
    assert client.get("/v1/speech/wake/busy").json() == {"busy": False}
    reply = client.post(
        "/v1/speech/wake/busy", json={"source": "mascote", "busy": True, "ttl": 10}
    )
    assert reply.json() == {"busy": True}
    assert client.get("/v1/speech/wake/busy").json() == {"busy": True}
    assert client.get("/v1/speech/wake").json()["busy"] is True
    client.post("/v1/speech/wake/busy", json={"source": "mascote", "busy": False})
    assert client.get("/v1/speech/wake/busy").json() == {"busy": False}
