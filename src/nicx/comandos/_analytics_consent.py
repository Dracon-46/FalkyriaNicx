"""Dedicated terminal consent for optional external usage analytics."""

from __future__ import annotations

import click
import tomlkit

from nicx.nucleo.config import AnalyticsConfig
from nicx.privacidade.textos import read_document

PROMPT = "Aperte Enter ou S para aceitar, ou N para recusar: "


def _consent_text() -> str:
    """The bundled consent text, as plain terminal text."""
    text = read_document("consentimento").replace("**", "").replace("## ", "")
    return "\n" + text.strip()


def ask_analytics_consent(host: str | None = None) -> bool:
    """Ask once per init; a deliberate Enter/S consents, EOF/cancellation does not."""
    stream = click.get_text_stream("stdin")
    if not stream.isatty():
        return False
    click.echo(_consent_text(), err=True)
    click.echo(
        "\nPolítica de privacidade completa: nicx legal privacidade\n"
        "Para mudar depois: nicx config set analytics.enabled false",
        err=True,
    )
    click.echo(f"Destino dos dados: {host or AnalyticsConfig().host}", err=True)
    while True:
        click.echo(PROMPT, nl=False, err=True)
        try:
            answer = stream.readline()
        except (EOFError, KeyboardInterrupt):
            click.echo(err=True)
            return False
        if not answer:
            return False
        answer = answer.strip().lower()
        if answer in ("", "s", "sim", "y", "yes"):
            return True
        if answer in ("n", "nao", "não", "no"):
            return False
        click.echo("Aperte Enter, digite S ou digite N.", err=True)


def apply_analytics_choice(content: str, choice: bool | None, *, prompt: bool) -> str:
    """Persist an explicit flag or terminal choice in generated/copied TOML."""
    if choice is None:
        if not prompt or not click.get_text_stream("stdin").isatty():
            # Defaults are off. Preserve an explicitly supplied config in
            # unattended init rather than rewriting unrelated input files.
            return content
        doc = tomlkit.parse(content)
        host = doc.get("analytics", {}).get("host", AnalyticsConfig().host)
        choice = ask_analytics_consent(str(host))
    doc = tomlkit.parse(content)
    if "analytics" not in doc:
        doc.add("analytics", tomlkit.table())
    doc["analytics"]["enabled"] = choice
    doc["analytics"]["choice_recorded"] = True
    return tomlkit.dumps(doc)
