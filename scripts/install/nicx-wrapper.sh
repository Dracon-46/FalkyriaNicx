#!/usr/bin/env bash
# nicx-wrapper.sh — ligado em ~/.local/bin/nicx pelo instalador.
# Acha a instalação (mesmo fora de ~/.nicx) e executa o nicx do ambiente dela.

# The install root is the parent of the folder holding this script; follow
# the ~/.local/bin symlink with plain `readlink` (macOS has no `readlink -f`).
self="$0"
while [[ -L "$self" ]]; do
    target="$(readlink "$self")"
    case "$target" in
        /*) self="$target" ;;
        *) self="$(dirname "$self")/$target" ;;
    esac
done
install_root="$(cd "$(dirname "$self")/.." 2>/dev/null && pwd -P)"

if [[ -z "${NICX_HOME:-}" && -n "$install_root" && -d "$install_root/.venv" ]]; then
    # Only a non-default root needs NICX_HOME exported; the default one is
    # what the runtime picks by itself (or its XDG location).
    if [[ "$install_root" != "$(cd "$HOME" && pwd -P)/.nicx" ]]; then
        export NICX_HOME="$install_root"
    fi
    VENV="$install_root/.venv"
else
    VENV="${NICX_HOME:-$HOME/.nicx}/.venv"
fi

if [[ ! -x "$VENV/bin/nicx" ]]; then
    echo "nicx: ambiente não encontrado em $VENV" >&2
    echo "Rode o instalador de novo: curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash" >&2
    exit 1
fi

# Apps started from Finder, Launchpad or launchd get a bare PATH; Nicx
# needs to find `ollama` (and `uv`) to start the local model by itself.
for dir in "$HOME/.local/bin" /opt/homebrew/bin /usr/local/bin \
    /Applications/Ollama.app/Contents/Resources \
    "$HOME/Applications/Ollama.app/Contents/Resources"; do
    if [[ -d "$dir" ]]; then
        case ":$PATH:" in
            *":$dir:"*) ;;
            *) PATH="$PATH:$dir" ;;
        esac
    fi
done
export PATH

exec "$VENV/bin/nicx" "$@"
