"""Outlook / Microsoft 365 connector — reads email via IMAP with app password.

Thin subclass of GmailIMAPConnector that defaults to the Outlook IMAP host
and relabels documents with source='outlook'.

Setup: enable 2FA on your Microsoft account, then generate an app password
at https://account.microsoft.com/security
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, Optional

import httpx

from nicx.conectores._stubs import Document
from nicx.conectores.gmail_imap import GmailIMAPConnector
from nicx.nucleo.config import DEFAULT_CONFIG_DIR
from nicx.nucleo.registry import ConnectorRegistry

_DEFAULT_CREDENTIALS_PATH = str(DEFAULT_CONFIG_DIR / "connectors" / "outlook.json")

_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def _graph_api_event_create(token: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create an event on the user's calendar (Microsoft Graph ``POST /me/events``).

    Only works with an OAuth token that has ``Calendars.ReadWrite``; the IMAP
    app password this connector uses for mail cannot do it.
    """
    resp = httpx.post(
        f"{_GRAPH_API_BASE}/me/events",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


@ConnectorRegistry.register("outlook")
class OutlookConnector(GmailIMAPConnector):
    """Outlook connector using IMAP + app password."""

    connector_id = "outlook"
    display_name = "Outlook / Microsoft 365"
    _default_imap_host = "outlook.office365.com"

    def __init__(
        self,
        email_address: str = "",
        app_password: str = "",
        credentials_path: str = "",
        *,
        max_messages: int = 500,
    ) -> None:
        super().__init__(
            email_address,
            app_password,
            credentials_path or _DEFAULT_CREDENTIALS_PATH,
            max_messages=max_messages,
        )

    def auth_url(self) -> str:
        return "https://account.microsoft.com/security"

    def sync(
        self,
        *,
        since: Optional[datetime] = None,
        cursor: Optional[str] = None,
    ) -> Iterator[Document]:
        for doc in super().sync(since=since, cursor=cursor):
            doc.source = "outlook"
            doc.doc_id = doc.doc_id.replace("gmail:", "outlook:", 1)
            yield doc
