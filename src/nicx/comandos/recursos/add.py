"""``nicx add`` — adiciona um servidor MCP conhecido (o mesmo da página Extensões)."""

from __future__ import annotations

import sys

import click
from rich.console import Console


@click.command()
@click.argument("server_name")
@click.option("--key", default=None, help="Chave de API ou token do servidor.")
@click.option(
    "--args",
    "extra_args",
    default=None,
    help="Argumentos extras (separados por vírgula), ex.: a pasta do filesystem.",
)
def add(server_name: str, key: str | None, extra_args: str | None) -> None:
    """Adiciona um servidor MCP às extensões do Nicx.

    Atalhos para os servidores MCP mais comuns:

    \b
      nicx add github --key TOKEN
      nicx add filesystem --args C:/Users/voce/Documentos
      nicx add slack --key TOKEN

    O servidor entra em ~/.nicx/mcp.json; com o Nicx aberto, ligue-o na página
    Extensões (ou reinicie o Nicx).
    """
    from nicx.extensoes import catalogo_mcp
    from nicx.extensoes import mcp as extensoes_mcp

    console = Console(stderr=True)

    modelo = catalogo_mcp.modelo(server_name)
    if modelo is None:
        console.print(f"[red]Servidor MCP desconhecido: {server_name}[/red]")
        console.print("[dim]Servidores conhecidos:[/dim]")
        for m in catalogo_mcp.CATALOGO:
            console.print(f"  [cyan]{m.chave}[/cyan] — {m.descricao}")
        sys.exit(1)

    args = list(modelo.args)
    if extra_args:
        args.extend(a.strip() for a in extra_args.split(",") if a.strip())
    env = {}
    for chave in modelo.env:
        if key:
            env[chave] = key
        else:
            console.print(
                f"[yellow]Dica: passe --key para definir {chave}"
                " (ou defina a variável de ambiente).[/yellow]"
            )

    servidor = extensoes_mcp.Servidor(
        nome=modelo.chave,
        comando=modelo.comando,
        args=args,
        env=env,
        confianca=modelo.confianca,
        descricao=modelo.descricao,
    )
    existente = next(
        (s for s in extensoes_mcp.listar() if s.nome == modelo.chave), None
    )
    try:
        if existente is not None:
            extensoes_mcp.atualizar(existente.id, servidor)
        else:
            extensoes_mcp.criar(servidor)
    except extensoes_mcp.ServidorInvalido as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    console.print(
        f"[green]Servidor MCP adicionado: {modelo.chave}[/green]\n"
        f"  Arquivo: {extensoes_mcp.caminho()}\n"
        f"  {modelo.descricao}"
    )
    if modelo.pede_args and not extra_args:
        console.print(f"  [dim]Complete com --args ({modelo.pede_args}).[/dim]")


__all__ = ["add"]
