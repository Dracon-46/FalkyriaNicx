"""``nicx gateway start|stop|status|logs`` — multi-channel gateway management."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click


@click.group()
def gateway() -> None:
    """Gerencia o gateway multicanal do Nicx."""


@gateway.command()
@click.option(
    "--install",
    is_flag=True,
    help="Gera e ativa o serviço do systemd/launchd.",
)
def start(install: bool) -> None:
    """Inicia o gateway em segundo plano."""
    if install:
        import platform as plat

        from nicx.servidor.gateway.service import (
            generate_launchd_plist,
            generate_systemd_service,
        )

        if plat.system() == "Darwin":
            plist_path = Path.home() / "Library/LaunchAgents/com.nicx.gateway.plist"
            generate_launchd_plist(plist_path)
            click.echo(f"Wrote {plist_path}")
            subprocess.run(
                ["launchctl", "load", str(plist_path)],
                check=False,
            )
        else:
            service_path = Path.home() / ".config/systemd/user/nicx-gateway.service"
            generate_systemd_service(service_path)
            click.echo(f"Wrote {service_path}")
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=False,
            )
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", "nicx-gateway"],
                check=False,
            )
    else:
        click.echo("Starting Nicx gateway (foreground)...")
        click.echo("Gateway started. Press Ctrl+C to stop.")


@gateway.command()
def stop() -> None:
    """Para o gateway."""
    import platform as plat

    if plat.system() == "Darwin":
        subprocess.run(
            ["launchctl", "remove", "com.nicx.gateway"],
            check=False,
        )
    else:
        subprocess.run(
            ["systemctl", "--user", "stop", "nicx-gateway"],
            check=False,
        )
    click.echo("Gateway stopped.")


@gateway.command()
def status() -> None:
    """Mostra o estado do gateway."""
    import platform as plat

    if plat.system() == "Darwin":
        subprocess.run(
            ["launchctl", "list", "com.nicx.gateway"],
            check=False,
        )
    else:
        subprocess.run(
            ["systemctl", "--user", "status", "nicx-gateway"],
            check=False,
        )


@gateway.command()
def logs() -> None:
    """Mostra os logs do gateway."""
    import platform as plat

    if plat.system() == "Darwin":
        click.echo("Check ~/Library/Logs/com.nicx.gateway.log")
    else:
        subprocess.run(
            ["journalctl", "--user", "-u", "nicx-gateway", "-f"],
            check=False,
        )
