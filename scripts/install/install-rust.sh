#!/usr/bin/env bash
# install-rust.sh — install Rust toolchain via rustup if cargo not present.
#
# Idempotent: exits 0 immediately if cargo is on PATH.

set -euo pipefail

# A previous rustup install may not be on a detached process's PATH.
if [[ -x "$HOME/.cargo/bin/cargo" ]]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

if command -v cargo >/dev/null 2>&1; then
    echo "install-rust.sh: cargo already present, skipping"
    exit 0
fi

echo "install-rust.sh: installing Rust toolchain via rustup..."
# --no-modify-path: build-extension.sh adds ~/.cargo/bin itself, so the
# user's shell files stay untouched. On macOS the linker comes from the
# Xcode Command Line Tools, which install.sh already required (git).
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs |
    sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable

if [[ -d "$HOME/.cargo/bin" ]]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

if ! command -v cargo >/dev/null 2>&1; then
    echo "install-rust.sh: cargo still not on PATH after install; check rustup output" >&2
    exit 1
fi
