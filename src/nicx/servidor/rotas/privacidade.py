"""Analytics endpoints used by the frontend.

The frontend never talks to the analytics destination directly: it reads
the consent state here, records the user's choice, and forwards events
through ``/capture`` so every event passes the same redaction and catalog
checks as backend events. ``/forget`` erases this installation's events
from Falkyria's servers (LGPD right to deletion).

Uses the server's normal API-key authentication when configured. The
Supabase publishable key returned by ``/dashboard-config`` is public by
design: row level security only lets it insert events.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from pathlib import Path
from typing import Any

import httpx
import tomlkit
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from nicx.nucleo.config import NicxConfig, load_config
from nicx.privacidade import POLICY_VERSION
from nicx.privacidade.bridge import EventBridge
from nicx.privacidade.client import AnalyticsClient
from nicx.privacidade.identity import (
    get_or_create_anon_id,
    is_analytics_enabled,
    reset_anon_id,
)
from nicx.privacidade.supabase_sink import forget_installation
from nicx.privacidade.textos import DOCUMENTS, read_document

logger = logging.getLogger(__name__)
_preference_lock = threading.RLock()


class AnalyticsIdentity(BaseModel):
    enabled: bool
    anon_id: str
    host: str
    key: str
    choice_recorded: bool = False
    policy_version: str = POLICY_VERSION


class AnalyticsPreference(BaseModel):
    """Only the analytics choice belongs here; contest details go elsewhere."""

    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


class AnalyticsEvent(BaseModel):
    """One frontend event; the catalog in ``nicx.privacidade.events`` filters it."""

    model_config = ConfigDict(extra="forbid")
    event: str = Field(min_length=1, max_length=64)
    properties: dict[str, Any] = Field(default_factory=dict)


class ForgetResult(BaseModel):
    removed: int
    anon_id: str


class DashboardConfig(BaseModel):
    supabase_url: str
    supabase_key: str
    policy_version: str


router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/identity", response_model=AnalyticsIdentity)
def get_identity(request: Request) -> AnalyticsIdentity:
    """Return the analytics identity for the current install.

    If analytics is disabled in config, still return a
    structurally valid response with ``enabled=False`` so the frontend
    can decide what to do; never throw.
    """
    cfg = getattr(request.app.state, "config", None) or load_config()
    enabled = is_analytics_enabled(cfg.analytics)
    anon_id = get_or_create_anon_id(cfg.analytics.anon_id_path) if enabled else ""
    return AnalyticsIdentity(
        enabled=enabled,
        anon_id=anon_id,
        host=cfg.analytics.host,
        key=cfg.analytics.key if enabled else "",
        choice_recorded=cfg.analytics.choice_recorded,
    )


def stop_analytics(app: FastAPI, *, wait: bool = True) -> None:
    """Detach the event bridge and close the current analytics client."""
    bridge = getattr(app.state, "analytics_bridge", None)
    client = getattr(app.state, "analytics_client", None)
    app.state.analytics_bridge = None
    app.state.analytics_client = None
    if client is not None and not wait:
        client.disable()
    if bridge is not None:
        try:
            bridge.stop()
        except Exception:
            logger.debug("Analytics bridge shutdown failed", exc_info=True)
    if client is not None:
        client.shutdown(wait=wait)


def configure_analytics(app: FastAPI, cfg: NicxConfig) -> None:
    """Apply a sharing choice immediately to this running server."""
    stop_analytics(app, wait=False)
    app.state.config = cfg
    if not is_analytics_enabled(cfg.analytics):
        return
    client = AnalyticsClient(cfg.analytics)
    app.state.analytics_client = client
    bus = getattr(app.state, "bus", None)
    if bus is not None and client.enabled:
        bridge = EventBridge(bus, client)
        app.state.analytics_bridge = bridge
        bridge.start()


@router.post("/preference", response_model=AnalyticsIdentity)
def set_preference(choice: AnalyticsPreference, request: Request) -> AnalyticsIdentity:
    """Persist an explicit UI choice and update analytics without restarting."""
    with _preference_lock:
        cfg = getattr(request.app.state, "config", None) or load_config()
        path = cfg._config_path
        temporary: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = (
                tomlkit.parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else tomlkit.document()
            )
            if "analytics" not in doc:
                doc.add("analytics", tomlkit.table())
            doc["analytics"]["enabled"] = choice.enabled
            doc["analytics"]["choice_recorded"] = True
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(tomlkit.dumps(doc))
            temporary.replace(path)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Could not save analytics preference: %s", exc)
            raise HTTPException(
                status_code=500, detail="Could not save your analytics choice."
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        cfg.analytics.enabled = choice.enabled
        cfg.analytics.choice_recorded = True
        load_config.cache_clear()
        client = getattr(request.app.state, "analytics_client", None)
        was_sending = client is not None and client.enabled
        if not choice.enabled and was_sending:
            # Record the revocation while the sender still runs: proof of
            # the user's choice, with no other data.
            client.capture(
                "analytics_consent",
                {"granted": False, "policy_version": POLICY_VERSION},
            )
        if (choice.enabled and not was_sending) or (
            not choice.enabled and client is not None
        ):
            configure_analytics(request.app, cfg)
        else:
            request.app.state.config = cfg
        new_client = getattr(request.app.state, "analytics_client", None)
        if choice.enabled and not was_sending and new_client is not None:
            new_client.capture(
                "analytics_consent",
                {"granted": True, "policy_version": POLICY_VERSION},
            )
        return get_identity(request)


@router.post("/capture", status_code=204)
def capture_event(payload: AnalyticsEvent, request: Request) -> Response:
    """Forward one frontend event; dropped silently without consent."""
    client = getattr(request.app.state, "analytics_client", None)
    if client is not None and client.enabled:
        client.capture(payload.event, payload.properties)
    return Response(status_code=204)


@router.post("/forget", response_model=ForgetResult)
def forget_installation_data(request: Request) -> ForgetResult:
    """Erase this installation's events remotely and start a new anonymous ID."""
    cfg = getattr(request.app.state, "config", None) or load_config()
    id_path = Path(cfg.analytics.anon_id_path)
    current = id_path.read_text(encoding="utf-8").strip() if id_path.exists() else ""
    removed = 0
    if current and cfg.analytics.host and cfg.analytics.key:
        try:
            removed = forget_installation(
                cfg.analytics.host, cfg.analytics.key, current
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Could not erase analytics data: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Não foi possível apagar seus dados agora. Tente de novo.",
            ) from exc
    new_id = reset_anon_id(id_path)
    if getattr(request.app.state, "analytics_client", None) is not None:
        configure_analytics(request.app, cfg)
    return ForgetResult(removed=removed, anon_id=new_id)


@router.get("/legal/{name}")
def legal_document(name: str) -> Response:
    """Serve a bundled legal text (privacy policy, terms, consent) as Markdown."""
    if name not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return Response(
        content=read_document(name), media_type="text/markdown; charset=utf-8"
    )


@router.get("/dashboard-config", response_model=DashboardConfig)
def dashboard_config(request: Request) -> DashboardConfig:
    """Public settings the analytics dashboard needs to sign admins in."""
    cfg = getattr(request.app.state, "config", None) or load_config()
    return DashboardConfig(
        supabase_url=cfg.analytics.host,
        supabase_key=cfg.analytics.key,
        policy_version=POLICY_VERSION,
    )


__all__ = ["configure_analytics", "router", "stop_analytics"]
