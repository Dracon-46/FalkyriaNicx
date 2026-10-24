"""External anonymous usage analytics.

Sends anonymized events to Falkyria's Supabase project, only after the
user consents, so the team can measure setup success, retention, feature
usage, and errors — without ever collecting chat content, prompts, file
paths, emails, IPs, or hardware identifiers.

Distinct from :mod:`nicx.registros.telemetria`, which stores local FLOPs and
energy metrics in a SQLite DB and never leaves the machine.

Disable: set ``[analytics] enabled = false`` in ``~/.nicx/config.toml``.
"""

from nicx.privacidade.aggregator import SessionAggregator
from nicx.privacidade.bridge import EventBridge
from nicx.privacidade.client import AnalyticsClient
from nicx.privacidade.identity import (
    get_or_create_anon_id,
    is_analytics_enabled,
    reset_anon_id,
)
from nicx.privacidade.redaction import hash_id, redact

# Version of docs/legal/politica-de-privacidade.md shown when asking for
# consent. Bump it whenever the policy changes so consent is asked again.
POLICY_VERSION = "2026-10-23"

__all__ = [
    "POLICY_VERSION",
    "AnalyticsClient",
    "EventBridge",
    "SessionAggregator",
    "get_or_create_anon_id",
    "is_analytics_enabled",
    "reset_anon_id",
    "redact",
    "hash_id",
]
