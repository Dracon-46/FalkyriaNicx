"""`nicx legal` — show the privacy policy, the terms of use or the consent text."""

from __future__ import annotations

import click

from nicx.legal import DOCUMENTS, read_document


@click.command(
    "legal",
    help=(
        "Mostra a política de privacidade, os termos de uso "
        "ou o termo de consentimento."
    ),
)
@click.argument(
    "documento",
    type=click.Choice(sorted(DOCUMENTS)),
    default="privacidade",
)
def legal(documento: str) -> None:
    click.echo(read_document(documento))
