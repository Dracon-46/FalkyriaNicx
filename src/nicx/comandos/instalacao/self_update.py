"""`nicx self-update` — upgrade Nicx from its Git checkout.

Editable Git checkouts recover release-tag history, fast-forward, and rebuild
Nicx in the running environment. The inexact sync preserves packages
previously installed through extras and dependency groups.

Package-index installs are refused: Nicx is not published on PyPI, and the
``nicx`` name there is not Falkyria's, so ``pip install --upgrade nicx``
could install someone else's code.

The detection logic is shared with the post-command "new version
available" hint in ``_version_check.py`` so both surfaces stay in sync.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

import nicx
from nicx.comandos.instalacao._install_detect import detect_install


def _fetch_url(repo_root: Path) -> str:
    """Return the URL ``git fetch`` and ``git pull`` would use, or ``""``."""
    result = subprocess.run(
        ["git", "ls-remote", "--get-url"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _update_git_checkout(repo_root: Path) -> int:
    """Repair version history and update without discarding local work."""
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if shallow.returncode:
        click.echo(shallow.stderr, err=True)
        return shallow.returncode
    if shallow.stdout.strip() not in {"true", "false"}:
        click.echo("Could not determine whether the checkout is shallow.", err=True)
        return 1

    # Fetching tags alone cannot make tags beyond a shallow boundary reachable.
    fetch = ["git", "fetch", "--tags"]
    if shallow.stdout.strip() == "true":
        fetch.append("--unshallow")
        click.echo("Restoring Git history for release version detection...")
    for command in (fetch, ["git", "pull", "--ff-only"]):
        result = subprocess.run(command, cwd=repo_root)
        if result.returncode:
            return result.returncode

    # Version metadata is baked at install time, so an up-to-date checkout also
    # needs a rebuild after history repair. The Unix installer keeps its venv
    # beside src/, not inside it: target the running venv, never a new src/.venv.
    click.echo("Rebuilding Nicx in the running Python environment...")
    if sys.prefix != sys.base_prefix:
        result = subprocess.run(
            [
                "uv",
                "sync",
                "--python",
                sys.executable,
                "--inexact",
                "--reinstall-package",
                "nicx",
            ],
            cwd=repo_root,
            env={**os.environ, "UV_PROJECT_ENVIRONMENT": sys.prefix},
        )
    else:
        # Editable installs in a non-venv interpreter have no uv project
        # environment to sync. Reinstall into that same interpreter instead.
        result = subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--reinstall-package",
                "nicx",
                "-e",
                ".",
            ],
            cwd=repo_root,
        )
    return result.returncode


@click.command(
    "self-update",
    help=(
        "Atualiza o Nicx pelo repositório Git: avança o branch e recompila. Com "
        "--check, só mostra o plano, sem executar."
    ),
)
@click.option(
    "--check",
    is_flag=True,
    help="Mostra o comando de atualização que rodaria, sem executar.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Não pede confirmação.",
)
def self_update(check: bool, yes: bool) -> None:
    info = detect_install()
    current = nicx.__version__

    click.echo(f"Current Nicx version: v{current}")
    click.echo(f"Install method: {info.kind}")
    if info.kind != "editable-git" or info.repo_root is None:
        raise click.ClickException(
            "O Nicx só se atualiza pelo repositório git. Ele não é publicado "
            "no PyPI, e o pacote `nicx` de lá não pertence à Falkyria."
        )

    remote = _fetch_url(info.repo_root)
    click.echo(f"Repository: {info.repo_root}")
    click.echo(f"Remote: {remote or '(none)'}")
    click.echo(
        "Upgrade plan: restore release-tag history, git pull --ff-only, "
        "then rebuild Nicx while preserving installed extras."
    )

    if check:
        return

    if not yes:
        if not click.confirm("\nRun the upgrade command now?", default=True):
            click.echo("Aborted.")
            sys.exit(1)

    click.echo("\nUpdating the source checkout...\n")

    try:
        returncode = _update_git_checkout(info.repo_root)
    except OSError as exc:
        raise click.ClickException(f"Não consegui rodar a atualização: {exc}") from exc

    if returncode != 0:
        click.echo(
            f"\nUpgrade command exited with code {returncode}. "
            "Inspect the output above for the failure mode.",
            err=True,
        )
        sys.exit(returncode)

    click.echo("\nUpgrade complete. Re-run `nicx --version` to confirm.")
