#!/usr/bin/env bash
# build-extension.sh — compila a extensão nativa nicx_rust no ambiente do Nicx.
#
# State files under $NICX_HOME/.state/:
#   extension-built   — atomic marker written on success
#   extension-failed  — written on failure with stderr tail
#   extension-build.log — captured stderr/stdout

set -euo pipefail

NICX_HOME="${NICX_HOME:-$HOME/.nicx}"
# Self-heal PATH for cargo and uv: install-rust.sh installs to ~/.cargo/bin
# and uv lives in ~/.local/bin, but a detached process may not have either.
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
SRC_DIR="$NICX_HOME/src"
VENV="$NICX_HOME/.venv"
STATE_DIR="$NICX_HOME/.state"
LOG="$STATE_DIR/extension-build.log"
BUILT="$STATE_DIR/extension-built"
FAILED="$STATE_DIR/extension-failed"
CRATE="$SRC_DIR/rust/crates/nicx-ponte"
MANIFEST="$CRATE/Cargo.toml"

mkdir -p "$STATE_DIR"

if [[ ! -f "$MANIFEST" ]]; then
    echo "build-extension.sh: manifest not found at $MANIFEST" > "$FAILED"
    exit 1
fi

# Half the cores by default, so a background build doesn't freeze the
# machine while the user works.
if [[ -z "${CARGO_BUILD_JOBS:-}" ]]; then
    cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
    case "$cores" in ''|*[!0-9]*) cores=2 ;; esac
    jobs=$(( cores / 2 ))
    if (( jobs < 1 )); then
        jobs=1
    fi
    export CARGO_BUILD_JOBS="$jobs"
fi

# Install the crate as a package into the SERVING venv ($NICX_HOME/.venv).
# `uv run maturin develop` would target the project venv ($SRC_DIR/.venv)
# instead, leaving the server without the extension. The crate's
# pyproject uses maturin as its build backend (release profile).
if uv pip install --python "$VENV/bin/python" --reinstall-package nicx-rust "$CRATE" >>"$LOG" 2>&1; then
    # Prove the serving venv can load it before declaring success.
    if "$VENV/bin/python" -c "import nicx_rust" >>"$LOG" 2>&1; then
        :
    else
        rc=$?
        {
            echo "build-extension.sh: the build succeeded but 'import nicx_rust'"
            echo "failed in $VENV (exit=$rc)"
            tail -n 50 "$LOG" 2>/dev/null || true
        } > "$FAILED"
        rm -f "$BUILT"
        exit "$rc"
    fi
    tmp="$BUILT.tmp"
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$tmp"
    mv "$tmp" "$BUILT"
    rm -f "$FAILED"
    exit 0
else
    rc=$?
    {
        echo "build-extension.sh failed (exit=$rc)"
        tail -n 50 "$LOG" 2>/dev/null || true
    } > "$FAILED"
    rm -f "$BUILT"
    exit "$rc"
fi
