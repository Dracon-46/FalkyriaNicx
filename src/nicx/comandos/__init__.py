"""Command-line interface for Nicx (Click-based)."""

from __future__ import annotations

import sys

import click

import nicx
from nicx.comandos.instalacao.scan import scan


def _invoked_command(argv: list[str]) -> str:
    """Return the first positional CLI token after global flags."""
    for arg in argv:
        if arg.startswith("-"):
            continue
        return arg
    return ""


# A data-boundary scan must be able to diagnose an invalid NICX_HOME.
# Importing the rest of the CLI eagerly would import core.config and resolve that
# path before the scan can turn the failure into a finding.
_DATA_BOUNDARY_BOOTSTRAP = (
    _invoked_command(sys.argv[1:]) == "scan" and "--data-boundaries" in sys.argv[1:]
)


def _should_skip_update_check(ctx: click.Context, argv: list[str]) -> bool:
    """Return true for commands whose diagnostics should remain local-only."""
    if "--research" in argv:
        return True
    return ctx.invoked_subcommand == "scan" and "--data-boundaries" in argv


@click.group(
    help="Nicx — modular AI assistant backend",
    invoke_without_command=True,
)
@click.version_option(version=nicx.__version__, prog_name="nicx")
@click.option("--verbose", is_flag=True, default=False, help="Enable debug logging")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-error output")
@click.option(
    "--pick-model",
    "pick_model_bare",
    is_flag=True,
    default=False,
    help=(
        "Bare ``nicx``: force interactive model list (overrides NICX_SKIP_MODEL_PICK)."
    ),
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, pick_model_bare: bool) -> None:
    """Top-level CLI group."""
    from nicx.comandos.log_config import setup_logging

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["pick_model_bare"] = pick_model_bare
    setup_logging(verbose=verbose, quiet=quiet)

    # Check for updates on interactive commands. The banner is noise in
    # demo recordings of ``nicx ask --research``, so skip it whenever
    # the research flag is in argv (cheap argv sniff — Click hasn't
    # parsed the subcommand's args yet at this point). Also skip
    # ``nicx scan --data-boundaries`` because it is intended to be a
    # local application-data diagnostic with no outbound calls.
    import sys

    skip_update_check = _should_skip_update_check(ctx, sys.argv[1:])
    if not quiet and ctx.invoked_subcommand and not skip_update_check:
        import threading

        from nicx.comandos.instalacao._version_check import check_for_updates

        # Run the PyPI version poll off the hot path: on a cache miss it does
        # a blocking urlopen (up to 3s) that otherwise delays every command,
        # notably `nicx serve` startup. It's best-effort and never
        # raises, and the nudge prints to stderr, so a daemon thread is safe —
        # for long-lived commands (serve) it finishes; for short commands that
        # exit first, the check is simply skipped this run (same as a miss).
        threading.Thread(
            target=check_for_updates,
            args=(ctx.invoked_subcommand,),
            daemon=True,
        ).start()

    # First-run guard — routes bare `nicx` to chat or init.
    if ctx.invoked_subcommand is None:
        from nicx.comandos.instalacao._first_run import check_and_route

        check_and_route(ctx)


cli.add_command(scan, "scan")
if not _DATA_BOUNDARY_BOOTSTRAP:
    from nicx.comandos.agentes.agent import agent
    from nicx.comandos.agentes.digest import digest
    from nicx.comandos.agentes.operators import operators
    from nicx.comandos.agentes.scheduler import scheduler
    from nicx.comandos.agentes.skill import skill
    from nicx.comandos.agentes.workflow import workflow
    from nicx.comandos.conversa.ask import ask
    from nicx.comandos.conversa.chat import chat
    from nicx.comandos.instalacao._bootstrap import bootstrap_cmd
    from nicx.comandos.instalacao.config import config
    from nicx.comandos.instalacao.doctor import doctor
    from nicx.comandos.instalacao.init import init
    from nicx.comandos.instalacao.legal import legal
    from nicx.comandos.instalacao.quickstart import quickstart
    from nicx.comandos.instalacao.self_update import self_update
    from nicx.comandos.recursos.add import add
    from nicx.comandos.recursos.channel import channel
    from nicx.comandos.recursos.channels import channels
    from nicx.comandos.recursos.connect import connect
    from nicx.comandos.recursos.feedback import feedback_group
    from nicx.comandos.recursos.memory import memory
    from nicx.comandos.recursos.model import model
    from nicx.comandos.recursos.registry import registry
    from nicx.comandos.recursos.telemetry import telemetry
    from nicx.comandos.recursos.tool import tool
    from nicx.comandos.recursos.vault import vault
    from nicx.comandos.sistema.daemon import restart, start, status, stop
    from nicx.comandos.sistema.gateway import gateway
    from nicx.comandos.sistema.gui import gui
    from nicx.comandos.sistema.host import host
    from nicx.comandos.sistema.serve import serve
    from nicx.comandos.voz.escuta import escuta, mascote

    cli.add_command(init, "init")
    cli.add_command(legal, "legal")
    cli.add_command(ask, "ask")
    cli.add_command(chat, "chat")
    cli.add_command(serve, "serve")
    cli.add_command(model, "model")
    cli.add_command(memory, "memory")
    cli.add_command(telemetry, "telemetry")
    cli.add_command(channel, "channel")
    cli.add_command(channels, "channels")
    cli.add_command(scheduler, "scheduler")
    cli.add_command(doctor, "doctor")
    cli.add_command(agent, "agents")
    cli.add_command(workflow, "workflow")
    cli.add_command(skill, "skill")
    cli.add_command(start, "start")
    cli.add_command(stop, "stop")
    cli.add_command(restart, "restart")
    cli.add_command(status, "status")
    cli.add_command(vault, "vault")
    cli.add_command(add, "add")
    cli.add_command(operators, "operators")
    cli.add_command(host, "host")
    cli.add_command(quickstart, "quickstart")
    cli.add_command(feedback_group, "feedback")
    cli.add_command(gateway, "gateway")
    cli.add_command(gui, "gui")
    cli.add_command(escuta, "escuta")
    cli.add_command(escuta, "wake")
    cli.add_command(mascote, "mascote")
    cli.add_command(tool, "tool")
    cli.add_command(registry, "registry")
    cli.add_command(config, "config")
    cli.add_command(connect, "connect")
    cli.add_command(digest, "digest")

    # Deep Research setup pulls the ingestion pipeline (embeddings/numpy). Guard
    # it so an import-time dependency failure cannot take down the whole CLI.
    try:
        from nicx.comandos.agentes.deep_research_setup import deep_research_setup

        cli.add_command(deep_research_setup, "deep-research-setup")
        cli.add_command(deep_research_setup, "research")
    except Exception as _dr_exc:
        import logging as _logging

        _logging.getLogger(__name__).debug(
            "deep-research command unavailable: %s", _dr_exc
        )
    cli.add_command(self_update, "self-update")
    cli.add_command(bootstrap_cmd, "_bootstrap")

    # Gateway CLI commands (lazy import to avoid pulling starlette)
    try:
        from nicx.comandos.sistema.auth import auth

        cli.add_command(auth, "auth")
    except ImportError:
        pass

    try:
        from nicx.comandos.sistema.tunnel import tunnel

        cli.add_command(tunnel, "tunnel")
    except ImportError:
        pass


def main() -> None:
    """Entry point registered as ``nicx`` console script."""
    import sys

    if sys.platform == "win32":
        for _stream in (sys.stdout, sys.stderr):
            if hasattr(_stream, "reconfigure"):
                try:
                    _stream.reconfigure(encoding="utf-8", errors="replace")
                except (AttributeError, OSError):
                    pass
    cli()


__all__ = ["cli", "main"]
