"""``nicx loja`` — assinar pacotes para a loja da Falkyria.

Uso da Falkyria: ``nicx loja assinar pacote.nicx.json`` gera o arquivo assinado
que vai para o Painel Falkyria (seção Loja). A chave privada fica em
``~/.falkyria-loja/`` e nunca sai deste PC.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console


@click.group()
def loja() -> None:
    """Assina e confere pacotes da loja da Falkyria."""


@loja.command("chave")
def chave() -> None:
    """Cria a chave de assinatura (uma vez só; não sobrescreve)."""
    from nicx.extensoes import assinatura

    console = Console(stderr=True)
    try:
        ident, publica = assinatura.gerar_chave()
    except FileExistsError as exc:
        console.print(f"[yellow]Já existe uma chave em {exc}. Nada mudou.[/yellow]")
        sys.exit(1)
    console.print(
        f"[green]Chave criada:[/green] {ident}\n"
        f"  Pública (vai em nicx/extensoes/loja_chaves.py): {publica}\n"
        f"  Privada: {assinatura.pasta_da_chave()} — faça uma cópia num lugar seguro."
    )


@loja.command("assinar")
@click.argument("arquivo", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--saida", type=click.Path(dir_okay=False, path_type=Path), default=None)
def assinar(arquivo: Path, saida: Path | None) -> None:
    """Confere o pacote e grava a versão assinada para o Painel."""
    from nicx.extensoes import assinatura, pacotes

    console = Console(stderr=True)
    try:
        pacote = pacotes.ler(arquivo.read_text(encoding="utf-8"))
    except pacotes.PacoteInvalido as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    if not pacote.get("versao"):
        console.print("[red]O pacote precisa de uma versão (ex.: 1.0.0).[/red]")
        sys.exit(1)
    problemas = pacotes.previa(pacote)["problemas"]
    if problemas:
        console.print("[red]Itens com problema:[/red]\n  " + "\n  ".join(problemas))
        sys.exit(1)
    try:
        assinado = assinatura.assinar(pacote)
    except FileNotFoundError:
        console.print("[red]Sem chave: rode `nicx loja chave` primeiro.[/red]")
        sys.exit(1)
    assinado["permissoes"] = pacotes.permissoes(pacote)
    destino = saida or arquivo.with_name(
        f"{pacote['id']}-{pacote['versao']}.assinado.json"
    )
    destino.write_text(
        json.dumps(assinado, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    console.print(
        f"[green]Assinado:[/green] {destino}\n"
        f"  {pacote['nome']} v{pacote['versao']} · chave {assinado['chave']}\n"
        "  Envie esse arquivo no Painel Falkyria, seção Loja."
    )


@loja.command("verificar")
@click.argument("arquivo", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def verificar(arquivo: Path) -> None:
    """Confere um arquivo assinado com as chaves que o Nicx aceita."""
    from nicx.extensoes import assinatura

    console = Console(stderr=True)
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        assinatura.verificar(
            dados["conteudo"], dados["sha256"], dados["assinatura"], dados["chave"]
        )
    except (ValueError, KeyError, TypeError) as exc:
        console.print(f"[red]Não confere: {exc}[/red]")
        sys.exit(1)
    console.print(f"[green]Confere:[/green] assinado pela chave {dados['chave']}.")


__all__ = ["loja"]
