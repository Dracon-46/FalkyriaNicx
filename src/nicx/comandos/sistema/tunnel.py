"""CLI commands for Cloudflare Tunnel management."""

from __future__ import annotations

import shutil
import subprocess
import sys

import click

from nicx.nucleo.config import DEFAULT_CONFIG_PATH


@click.group("tunnel", invoke_without_command=True)
@click.option("--port", default=8000, help="Porta local a expor pelo túnel.")
@click.pass_context
def tunnel(ctx: click.Context, port: int) -> None:
    """Inicia um túnel do Cloudflare ou gerencia a configuração dele."""
    if ctx.invoked_subcommand is not None:
        return
    # Default behavior: start the tunnel
    if not shutil.which("cloudflared"):
        click.echo("Erro: o cloudflared não está instalado.")
        click.echo(
            "Instale em: "
            "https://developers.cloudflare.com/"
            "cloudflare-one/connections/"
            "connect-networks/downloads/"
        )
        sys.exit(1)

    click.echo(f"Abrindo o túnel do Cloudflare para localhost:{port}...")
    click.echo("Aperte Ctrl+C para parar.\n")

    try:
        subprocess.run(
            [
                "cloudflared",
                "tunnel",
                "--url",
                f"http://localhost:{port}",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        click.echo("\nTunnel stopped.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Tunnel failed: {e}")
        sys.exit(1)


@tunnel.command("status")
def status() -> None:
    """Mostra a configuração atual do túnel."""
    config_path = DEFAULT_CONFIG_PATH
    if not config_path.exists():
        click.echo("No config file found.")
        return

    content = config_path.read_text()
    if "public_url" in content:
        for line in content.splitlines():
            if "public_url" in line:
                click.echo(f"Configured tunnel URL: {line.split('=', 1)[1].strip()}")
                return
    click.echo("No tunnel URL configured.")

    if shutil.which("cloudflared"):
        click.echo("cloudflared: installed")
    else:
        click.echo("cloudflared: not installed")
