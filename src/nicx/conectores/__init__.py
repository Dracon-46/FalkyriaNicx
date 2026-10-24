"""Data source connectors for Deep Research."""

from nicx.conectores._stubs import (
    Attachment,
    BaseConnector,
    Document,
    SyncStatus,
)
from nicx.conectores.store import KnowledgeStore

__all__ = ["Attachment", "BaseConnector", "Document", "KnowledgeStore", "SyncStatus"]

# Auto-register built-in connectors
import nicx.conectores.obsidian  # noqa: F401

try:
    import nicx.conectores.gmail  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.gmail_imap  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.gdrive  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import nicx.conectores.notion  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.granola  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.gcontacts  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.imessage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.apple_notes  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.apple_music  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.apple_contacts  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.slack_connector  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.outlook  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.imap  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.gcalendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.dropbox  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import nicx.conectores.whatsapp  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.oura  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.apple_health  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.strava  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.spotify  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.google_tasks  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.weather  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.github_notifications  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.hackernews  # noqa: F401
except ImportError:
    pass

try:
    import nicx.conectores.news_rss  # noqa: F401
except ImportError:
    pass
