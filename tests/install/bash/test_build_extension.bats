#!/usr/bin/env bats

setup() {
    TEST_TMPDIR=$(mktemp -d)
    export NICX_HOME="$TEST_TMPDIR/.nicx"
    mkdir -p "$NICX_HOME/.state"
    mkdir -p "$NICX_HOME/src/rust/crates/nicx-ponte"
    touch "$NICX_HOME/src/rust/crates/nicx-ponte/Cargo.toml"
    export UV_STUB_LOG="$TEST_TMPDIR/uv.log"
    : > "$UV_STUB_LOG"
    export PATH="$BATS_TEST_DIRNAME/stubs:$PATH"
    export SCRIPT="$BATS_TEST_DIRNAME/../../../scripts/install/build-extension.sh"
}

teardown() {
    [[ -n "${TEST_TMPDIR:-}" ]] && rm -rf "$TEST_TMPDIR"
}

@test "writes extension-built marker on success" {
    UV_STUB_EXIT=0 run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [ -f "$NICX_HOME/.state/extension-built" ]
}

@test "writes extension-failed marker on failure" {
    UV_STUB_EXIT=1 run bash "$SCRIPT"
    [ "$status" -ne 0 ]
    [ -f "$NICX_HOME/.state/extension-failed" ]
    [ -s "$NICX_HOME/.state/extension-failed" ]
}

@test "removes prior failed marker on success" {
    touch "$NICX_HOME/.state/extension-failed"
    UV_STUB_EXIT=0 run bash "$SCRIPT"
    [ ! -f "$NICX_HOME/.state/extension-failed" ]
    [ -f "$NICX_HOME/.state/extension-built" ]
}

@test "calls uv run maturin develop with the right manifest" {
    UV_STUB_EXIT=0 run bash "$SCRIPT"
    grep -q "run maturin develop -m" "$UV_STUB_LOG"
    grep -q "rust/crates/nicx-ponte/Cargo.toml" "$UV_STUB_LOG"
}

@test "atomic rename — no .tmp file left behind" {
    UV_STUB_EXIT=0 run bash "$SCRIPT"
    leftover=$(find "$NICX_HOME/.state" -name "*.tmp" 2>/dev/null | wc -l)
    [ "$leftover" -eq 0 ]
}
