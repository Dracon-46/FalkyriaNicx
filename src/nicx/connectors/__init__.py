"""Data source connectors for Deep Research."""

from nicx.connectors._stubs import (
    Attachment,
    BaseConnector,
    Document,
    SyncStatus,
)
from nicx.connectors.store import KnowledgeStore

__all__ = ["Attachment", "BaseConnector", "Document", "KnowledgeStore", "SyncStatus"]

# Auto-register built-in connectors
import nicx.connectors.obsidian  # noqa: F401

try:
    import nicx.connectors.gmail  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.gmail_imap  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.gdrive  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import nicx.connectors.notion  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.granola  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.gcontacts  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.imessage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.apple_notes  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.apple_music  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.apple_contacts  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.slack_connector  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.outlook  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.imap  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.gcalendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.dropbox  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import nicx.connectors.whatsapp  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.oura  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.apple_health  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.strava  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.spotify  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.google_tasks  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.weather  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.github_notifications  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.hackernews  # noqa: F401
except ImportError:
    pass

try:
    import nicx.connectors.news_rss  # noqa: F401
except ImportError:
    pass
