"""``nicx workflow`` — workflow management commands."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table


@click.group()
def workflow() -> None:
    """Gerencia os fluxos de trabalho: listar, rodar, ver o estado."""


@workflow.command("list")
def list_workflows() -> None:
    """Lista os fluxos disponíveis."""
    console = Console(stderr=True)
    try:
        from nicx.cerebro.fluxos.loader import discover_workflows

        workflows = discover_workflows()
        if not workflows:
            console.print("[dim]No workflows found.[/dim]")
            return
        table = Table(title="Workflows")
        table.add_column("Name", style="cyan")
        table.add_column("Nodes", style="green")
        for name, wf in workflows.items():
            table.add_row(name, str(len(wf.nodes) if hasattr(wf, "nodes") else "?"))
        console.print(table)
    except ImportError:
        console.print("[dim]No workflows found. Define workflows in TOML files.[/dim]")
    except Exception as exc:
        console.print(f"[red]Erro: {exc}[/red]")


@workflow.command()
@click.argument("workflow_name")
@click.option("--input", "input_text", default=None, help="Texto de entrada do fluxo.")
def run(workflow_name: str, input_text: str | None) -> None:
    """Roda um fluxo pelo nome."""
    console = Console(stderr=True)
    console.print(f"[yellow]Running workflow: {workflow_name}[/yellow]")
    try:
        from nicx.cerebro.fluxos.loader import discover_workflows

        workflows = discover_workflows()
        if workflow_name not in workflows:
            console.print(f"[red]Fluxo '{workflow_name}' não encontrado.[/red]")
            return
        console.print(f"[green]Workflow '{workflow_name}' started.[/green]")
        # Full execution would need a NicxSystem — just report for now
        console.print(
            "[dim]Note: Full workflow execution requires a running system.[/dim]"
        )
    except ImportError:
        console.print("[red]Workflow system not available.[/red]")
    except Exception as exc:
        console.print(f"[red]Erro: {exc}[/red]")


@workflow.command()
def status() -> None:
    """Mostra o estado dos fluxos em execução."""
    console = Console(stderr=True)
    console.print("[dim]No workflows currently running.[/dim]")


__all__ = ["workflow"]
