"""Deliver analytics events to Falkyria's Supabase project.

Events are queued in memory and posted in batches to the ``nicx_events``
table through Supabase's REST API on a background thread. The table's row
level security lets the publishable key insert well-formed events and nothing
else, so the key shipped inside the app can never read data back.

Delivery is best-effort: a network failure drops the batch instead of blocking
or crashing Nicx.
"""

from __future__ import annotations

import logging
import platform
import queue
import threading
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EVENTS_TABLE = "nicx_events"
FORGET_FUNCTION = "nicx_forget"


def _os_name() -> str:
    system = platform.system().lower()
    if system == "linux" and "microsoft" in platform.release().lower():
        return "wsl"
    return {"windows": "windows", "darwin": "darwin", "linux": "linux"}.get(
        system, "unknown"
    )


def _arch() -> str:
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64"}.get(
        machine, "aarch64" if machine == "aarch64" else "unknown"
    )


def install_context(app_version: str) -> dict[str, str]:
    """Columns stored with every event: Nicx version, OS and CPU architecture."""
    return {"app_version": app_version[:64], "os": _os_name(), "arch": _arch()}


def _headers(key: str) -> dict[str, str]:
    headers = {"apikey": key, "Content-Type": "application/json"}
    # Legacy anon keys are JWTs and also go in the bearer header; the newer
    # ``sb_publishable_`` keys must not.
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def forget_installation(url: str, key: str, anon_id: str, timeout: float = 10.0) -> int:
    """Delete every event this installation sent. Returns how many were removed."""
    response = httpx.post(
        f"{url.rstrip('/')}/rest/v1/rpc/{FORGET_FUNCTION}",
        json={"p_anon_id": anon_id},
        headers=_headers(key),
        timeout=timeout,
    )
    response.raise_for_status()
    return int(response.json() or 0)


class SupabaseSink:
    """Batching event sender exposing ``capture``/``flush``/``shutdown``."""

    def __init__(
        self,
        url: str,
        key: str,
        *,
        context: dict[str, str] | None = None,
        flush_at: int = 100,
        flush_interval: float = 30.0,
        max_queue_size: int = 10_000,
        timeout: float = 5.0,
    ) -> None:
        self._endpoint = f"{url.rstrip('/')}/rest/v1/{EVENTS_TABLE}"
        self._headers = {**_headers(key), "Prefer": "return=minimal"}
        self._context = context or {}
        self._flush_at = max(1, flush_at)
        self._flush_interval = flush_interval
        self._timeout = timeout
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=max_queue_size)
        self._send_lock = threading.Lock()
        self._wake = threading.Event()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="nicx-analytics", daemon=True
        )
        self._thread.start()

    def capture(self, distinct_id: str, event: str, properties: dict[str, Any]) -> None:
        if self._stopped.is_set():
            return
        row = {
            "anon_id": distinct_id,
            "event": event,
            "properties": properties,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "platform": str(properties.get("platform", "cli"))[:32],
            **self._context,
        }
        try:
            self._queue.put_nowait(row)
        except queue.Full:
            return
        if self._queue.qsize() >= self._flush_at:
            self._wake.set()

    def flush(self) -> None:
        """Send everything queued so far. Safe to call from any thread."""
        with self._send_lock:
            while batch := self._drain():
                self._post(batch)

    def shutdown(self) -> None:
        self._stopped.set()
        self._wake.set()
        self._thread.join(timeout=self._timeout)
        self.flush()

    def _drain(self, limit: int = 500) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        while len(batch) < limit:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _post(self, batch: list[dict[str, Any]]) -> None:
        try:
            response = httpx.post(
                self._endpoint,
                json=batch,
                headers=self._headers,
                timeout=self._timeout,
            )
            if response.status_code >= 400:
                logger.debug(
                    "Analytics batch rejected (%s): %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.debug("Analytics batch not delivered: %s", exc)

    def _run(self) -> None:
        while not self._stopped.is_set():
            self._wake.wait(self._flush_interval)
            self._wake.clear()
            if self._stopped.is_set():
                return
            self.flush()
