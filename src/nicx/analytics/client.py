"""Analytics client.

A thin adapter over :class:`~nicx.analytics.supabase_sink.SupabaseSink` that:
  - Initialises lazily and only if analytics is enabled.
  - Pipes every capture through :mod:`redaction` and :mod:`events` for
    PII stripping and structural validation.
  - Fails silently — analytics must never break the host application.

The sink handles batching, async send on a background thread, and
silent failure on network errors. We layer
"never crash the app" on top by wrapping every call in try/except.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from nicx.analytics.events import validate_event
from nicx.analytics.identity import (
    get_or_create_anon_id,
    is_analytics_enabled,
)
from nicx.analytics.redaction import redact
from nicx.core.config import AnalyticsConfig

logger = logging.getLogger(__name__)


class AnalyticsClient:
    """Send anonymized usage events to Falkyria's Supabase project.

    Construct once at server / CLI startup, share for the process
    lifetime, call :meth:`shutdown` on exit to flush pending events.
    """

    def __init__(self, config: AnalyticsConfig, anon_id: str | None = None) -> None:
        self.config = config
        self._enabled = is_analytics_enabled(config)
        self.anon_id = (
            anon_id or get_or_create_anon_id(config.anon_id_path)
            if self._enabled
            else ""
        )
        self._lock = threading.Lock()
        self._sink: Any = None
        if self._enabled:
            self._init_sdk()

    def _init_sdk(self) -> None:
        try:
            import nicx
            from nicx.analytics.supabase_sink import SupabaseSink, install_context

            self._sink = SupabaseSink(
                url=self.config.host,
                key=self.config.key,
                context=install_context(nicx.__version__),
                flush_at=self.config.flush_at_size,
                flush_interval=self.config.flush_interval_seconds,
            )
            logger.debug(
                "Analytics initialised host=%s anon_id=%s…",
                self.config.host,
                self.anon_id[:8],
            )
        except Exception as exc:
            logger.debug("Analytics init failed (%s); analytics disabled", exc)
            self._sink = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._sink is not None

    def capture(
        self,
        event_name: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Send one event. Unknown events are silently dropped.

        Runs through redaction → event-spec validation → SDK capture.
        Failures at any stage are swallowed; analytics is best-effort.
        """
        if not self.enabled:
            return
        try:
            raw = properties or {}
            cleaned = redact(raw)
            validated = validate_event(event_name, cleaned)
            if validated is None:
                logger.debug("Dropped unknown analytics event: %s", event_name)
                return
            self._sink.capture(self.anon_id, event_name, validated)
        except Exception as exc:
            logger.debug("Analytics capture failed for %s: %s", event_name, exc)

    def flush(self) -> None:
        """Force-flush queued events. Safe to call repeatedly."""
        if self._sink is None:
            return
        try:
            self._sink.flush()
        except Exception:
            pass

    def disable(self) -> None:
        """Stop accepting events without waiting for network delivery."""
        with self._lock:
            self._enabled = False

    def shutdown(self, *, wait: bool = True) -> None:
        """Close the SDK, optionally moving network cleanup off the caller."""
        with self._lock:
            sdk = self._sink
            self._sink = None
            self._enabled = False
        if sdk is None:
            return

        def close_sdk() -> None:
            try:
                sdk.flush()
                sdk.shutdown()
            except Exception:
                pass

        if wait:
            close_sdk()
        else:
            threading.Thread(
                target=close_sdk, name="analytics-shutdown", daemon=True
            ).start()


__all__ = ["AnalyticsClient"]
