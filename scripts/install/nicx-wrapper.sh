#!/usr/bin/env bash
# nicx-wrapper.sh — symlinked to ~/.local/bin/nicx.
# Activates the managed venv and execs the real nicx CLI.

NICX_HOME="${NICX_HOME:-$HOME/.nicx}"
VENV="$NICX_HOME/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "nicx: venv not found at $VENV" >&2
    echo "Re-run the installer: curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash" >&2
    exit 1
fi

exec "$VENV/bin/nicx" "$@"
