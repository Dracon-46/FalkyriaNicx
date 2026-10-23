"""Legal texts shipped with Nicx (privacy policy, terms, consent prompt).

They live inside the package so the app, the CLI and the installer can show
them offline, whatever the state of the repository or website.
"""

from __future__ import annotations

from importlib import resources

DOCUMENTS = {
    "privacidade": "politica-de-privacidade.md",
    "termos": "termos-de-uso.md",
    "consentimento": "consentimento.md",
}


def read_document(name: str) -> str:
    """Return a legal document's Markdown by short name (see ``DOCUMENTS``)."""
    filename = DOCUMENTS[name]
    return resources.files(__name__).joinpath(filename).read_text(encoding="utf-8")


__all__ = ["DOCUMENTS", "read_document"]
