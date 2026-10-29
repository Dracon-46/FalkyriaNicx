#!/usr/bin/env bats

# Requires Python with tomlkit, as does the installed application. Set
# NICX_TEST_PYTHON to an existing project venv when running locally.

setup() {
    export NICX_TEST_PYTHON="${NICX_TEST_PYTHON:-$(command -v python3)}"
    export PYTHONPATH="$BATS_TEST_DIRNAME/../../../src"
    unset NICX_CONFIG XDG_DATA_HOME
    TEST_TMPDIR=$(mktemp -d)
    export FAKE_HOME="$TEST_TMPDIR/home"
    mkdir -p "$FAKE_HOME"
    export HOME="$FAKE_HOME"
    export NICX_HOME="$FAKE_HOME/.nicx"

    export STUBS_DIR="$BATS_TEST_DIRNAME/stubs"
    # Use a copy of stubs without uv-style real binaries that might be on the host.
    # Just put our stubs first in PATH.
    export PATH="$STUBS_DIR:/usr/bin:/bin"

    # Nicx ships with no analytics destination; consent tests need a fake one.
    export NICX_ANALYTICS_HOST="https://analytics.example.invalid"
    export NICX_ANALYTICS_KEY="phc_test"

    export GIT_STUB_LOG="$TEST_TMPDIR/git.log"
    export OLLAMA_STUB_LOG="$TEST_TMPDIR/ollama.log"
    export UV_STUB_LOG="$TEST_TMPDIR/uv.log"
    export CURL_STUB_LOG="$TEST_TMPDIR/curl.log"
    export NICX_STUB_LOG="$TEST_TMPDIR/nicx.log"
    : > "$GIT_STUB_LOG"
    : > "$OLLAMA_STUB_LOG"
    : > "$UV_STUB_LOG"
    : > "$CURL_STUB_LOG"

    # uv stub needs to fake creating a venv with a nicx binary.
    # Replace the stubs/uv with one that creates the venv tree on `venv` command.
    # Since we don't want to mutate the real stub, override via a per-test stub dir.
    export PER_TEST_STUBS="$TEST_TMPDIR/stubs"
    mkdir -p "$PER_TEST_STUBS"
    cat "$STUBS_DIR/uv" > "$PER_TEST_STUBS/uv"
    chmod +x "$PER_TEST_STUBS/uv"
    # Wrap uv to handle 'venv' specially.
    cat > "$PER_TEST_STUBS/uv" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "\$UV_STUB_LOG"
case "\$1" in
    venv)
        # uv venv [--python X.Y] <path>
        # Find the path arg (last non-flag).
        for a in "\$@"; do
            if [[ "\$a" != --* ]] && [[ "\$a" != -* ]] && [[ "\$a" != "venv" ]] && [[ ! "\$a" =~ ^[0-9]+\\.[0-9]+\$ ]]; then
                venv_path="\$a"
            fi
        done
        if [[ -n "\$venv_path" ]]; then
            mkdir -p "\$venv_path/bin"
            cat > "\$venv_path/bin/nicx" <<'EOJ'
#!/usr/bin/env bash
# fake nicx for tests
echo "\$@" >> "\$NICX_STUB_LOG"
# Model the pre-consent CLI, which cannot validate the new schema key.
if [[ "\$*" == 'config set analytics.choice_recorded true' ]]; then
    echo "Error: Unknown config key: 'analytics.choice_recorded'" >&2
    exit 1
fi
echo "fake nicx: \$@"
exit 0
EOJ
            chmod +x "\$venv_path/bin/nicx"
            cat > "\$venv_path/bin/python" <<'EOJ'
#!/usr/bin/env bash
# Run the real persistence code using an interpreter with app dependencies.
exec "\$NICX_TEST_PYTHON" "\$@"
EOJ
            chmod +x "\$venv_path/bin/python"
        fi
        ;;
esac
exit 0
EOF
    chmod +x "$PER_TEST_STUBS/uv"

    # Copy other stubs, with the per-test uv first.
    cp "$STUBS_DIR"/{git,curl,ollama,cargo,rustup} "$PER_TEST_STUBS/"
    chmod +x "$PER_TEST_STUBS"/*

    export PATH="$PER_TEST_STUBS:/usr/bin:/bin"

    export SCRIPT="$BATS_TEST_DIRNAME/../../../scripts/install/install.sh"
}

teardown() {
    [[ -n "${TEST_TMPDIR:-}" ]] && rm -rf "$TEST_TMPDIR"
}

assert_analytics_preference() {
    "$NICX_TEST_PYTHON" - "$1" "$2" "$3" <<'PY'
import sys
from pathlib import Path

import tomlkit

analytics = tomlkit.parse(Path(sys.argv[1]).read_text())["analytics"]
assert bool(analytics["enabled"]) is (sys.argv[2] == "true")
assert bool(analytics.get("choice_recorded", False)) is (sys.argv[3] == "true")
PY
}

@test "unattended install sends no analytics and persists disabled" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ ! -f "$NICX_HOME/anon_id" ]
    assert_analytics_preference "$NICX_HOME/config.toml" false false
}

@test "without a configured destination there is no prompt and no beacon" {
    export NICX_ANALYTICS_HOST="" NICX_ANALYTICS_KEY=""
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["\n"]'
    [ "$status" -eq 0 ]
    [[ "$output" != *"Digite S para aceitar"* ]]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ ! -f "$NICX_HOME/anon_id" ]
}

@test "explicit analytics flag sends beacons and persists enabled" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --analytics
    [ "$status" -eq 0 ]
    grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ -s "$NICX_HOME/anon_id" ]
    assert_analytics_preference "$NICX_HOME/config.toml" true true
}

@test "S at dedicated terminal prompt consents before the first beacon" {
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["S\n"]'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Digite S para aceitar ou N para recusar"* ]]
    grep -q '"event":"install_started"' "$CURL_STUB_LOG"
    assert_analytics_preference "$NICX_HOME/config.toml" true true
}

@test "Enter at the prompt leaves analytics off and undecided" {
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["\n"]'
    [ "$status" -eq 0 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ ! -f "$NICX_HOME/anon_id" ]
    assert_analytics_preference "$NICX_HOME/config.toml" false false
}

@test "non-interactive mode never prompts and keeps analytics off" {
    NICX_INSTALL_NONINTERACTIVE=1 run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["S\n"]'
    [ "$status" -eq 0 ]
    [[ "$output" != *"Digite S para aceitar"* ]]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    assert_analytics_preference "$NICX_HOME/config.toml" false false
}

@test "N at terminal prompt declines every installer beacon" {
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["N\n"]'
    [ "$status" -eq 0 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ ! -f "$NICX_HOME/anon_id" ]
    assert_analytics_preference "$NICX_HOME/config.toml" false true
}

@test "invalid answer retries without silently consenting" {
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["invalid\n", "n\n"]'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Digite S, N ou só Enter."* ]]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
}

@test "terminal EOF is different from pressing Enter" {
    run python3 "$BATS_TEST_DIRNAME/run_installer_pty.py" "$SCRIPT" '["\u0004"]'
    [ "$status" -eq 0 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    [ ! -f "$NICX_HOME/anon_id" ]
    assert_analytics_preference "$NICX_HOME/config.toml" false false
}

@test "declining on a rerun persists despite skipped config creation" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --analytics
    [ "$status" -eq 0 ]
    : > "$NICX_STUB_LOG"
    : > "$CURL_STUB_LOG"
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --no-analytics
    [ "$status" -eq 0 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
    ! grep -q '_bootstrap' "$NICX_STUB_LOG"
    assert_analytics_preference "$NICX_HOME/config.toml" false true
}

@test "rerun saves consent with an older CLI and preserves existing TOML" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    cat > "$NICX_HOME/config.toml" <<'TOML'
# Preserve user settings and comments.
[engine]
default = "ollama"
[analytics]
enabled = false # Previous choice.
flush_at_size = 7
TOML
    run "$NICX_HOME/.venv/bin/nicx" config set analytics.choice_recorded true
    [ "$status" -eq 1 ]
    : > "$NICX_STUB_LOG"
    : > "$UV_STUB_LOG"
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --analytics
    [ "$status" -eq 0 ]
    [ ! -s "$UV_STUB_LOG" ]
    [ ! -s "$NICX_STUB_LOG" ]
    assert_analytics_preference "$NICX_HOME/config.toml" true true
    grep -q '# Preserve user settings and comments.' "$NICX_HOME/config.toml"
    grep -q '# Previous choice.' "$NICX_HOME/config.toml"
    grep -q 'default = "ollama"' "$NICX_HOME/config.toml"
    grep -q 'flush_at_size = 7' "$NICX_HOME/config.toml"
}

@test "consent respects NICX_CONFIG instead of changing the default config" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --no-analytics
    [ "$status" -eq 0 ]
    export NICX_CONFIG="$TEST_TMPDIR/custom config.toml"
    printf '# Custom config\n[engine]\ndefault = "ollama"\n' > "$NICX_CONFIG"
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --analytics
    [ "$status" -eq 0 ]
    assert_analytics_preference "$NICX_CONFIG" true true
    assert_analytics_preference "$NICX_HOME/config.toml" false true
    grep -q '# Custom config' "$NICX_CONFIG"
}

@test "consent follows the runtime XDG path when NICX_HOME is unset" {
    unset NICX_HOME
    export XDG_DATA_HOME="$TEST_TMPDIR/xdg data"
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --analytics
    [ "$status" -eq 0 ]
    assert_analytics_preference "$XDG_DATA_HOME/nicx/config.toml" true true
    [ ! -f "$HOME/.nicx/config.toml" ]
}

@test "contradictory analytics flags are rejected" {
    run bash "$SCRIPT" --analytics --no-analytics
    [ "$status" -eq 2 ]
    ! grep -q '/rest/v1/nicx_events' "$CURL_STUB_LOG"
}

@test "refuses to run as root" {
    # EUID is readonly in bash, so we stub `id` to return uid 0 instead.
    local root_stubs="$TEST_TMPDIR/root_stubs"
    mkdir -p "$root_stubs"
    cp "$PER_TEST_STUBS"/* "$root_stubs/"
    cat > "$root_stubs/id" <<'IDEOF'
#!/usr/bin/env bash
if [[ "$1" == "-u" ]]; then echo 0; else echo "uid=0(root) gid=0(root) groups=0(root)"; fi
IDEOF
    chmod +x "$root_stubs/id"
    PATH="$root_stubs:/usr/bin:/bin" run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi "root"
}

@test "creates ~/.nicx directory tree" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    [ -d "$NICX_HOME/src" ]
    [ -d "$NICX_HOME/.state" ]
    [ -d "$NICX_HOME/.scripts" ]
}

@test "writes install-state.json on success" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    [ -f "$NICX_HOME/.state/install-state.json" ]
}

@test "calls git clone for the Nicx repo" {
    run bash "$SCRIPT" --no-bg-orchestrator
    grep -q "clone" "$GIT_STUB_LOG"
}

@test "creates nicx symlink in ~/.local/bin" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    [ -L "$FAKE_HOME/.local/bin/nicx" ] || [ -f "$FAKE_HOME/.local/bin/nicx" ]
}

@test "is idempotent — second run skips completed steps" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    : > "$GIT_STUB_LOG"
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    ! grep -q "clone" "$GIT_STUB_LOG"
}

@test "detects WSL2 and writes platform note to install-state" {
    NICX_FORCE_WSL=1 run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    grep -q "wsl" "$NICX_HOME/.state/install-state.json"
}

@test "fails loudly when git is missing" {
    # O instalador acha o Homebrew pelo caminho fixo e o soma ao PATH; nas
    # máquinas Mac do GitHub ele já traz o git, então não dá para simular a
    # falta do git ali (e com Homebrew o git realmente existe).
    if [[ -x /opt/homebrew/bin/git || -x /usr/local/bin/git ]] &&        [[ -x /opt/homebrew/bin/brew || -x /usr/local/bin/brew ]]; then
        skip "o Homebrew desta máquina já traz o git"
    fi
    # Build a minimal stubs dir that has curl/uv/ollama but NO git.
    # We must NOT include /usr/bin or /bin in PATH because those dirs have real
    # git binaries on this system. Instead, provide only the commands the script
    # needs before it reaches the `need git` check (id, cat, bash).
    local no_git_stubs="$TEST_TMPDIR/no_git_stubs"
    mkdir -p "$no_git_stubs"
    for f in curl uv ollama cargo rustup; do
        cp "$PER_TEST_STUBS/$f" "$no_git_stubs/"
        chmod +x "$no_git_stubs/$f"
    done
    # Provide minimal system utilities (no git) using explicit symlinks.
    cat > "$no_git_stubs/id" <<'IDEOF'
#!/bin/bash
echo "1000"
IDEOF
    chmod +x "$no_git_stubs/id"
    ln -sf /bin/cat "$no_git_stubs/cat"
    ln -sf /bin/bash "$no_git_stubs/bash"
    PATH="$no_git_stubs" run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi "git"
}

@test "--force re-runs completed steps" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    : > "$GIT_STUB_LOG"
    run bash "$SCRIPT" --no-bg-orchestrator --force
    [ "$status" -eq 0 ]
    # With --force, the existing checkout is updated (git pull) instead of
    # a re-clone, which git refuses into a non-empty directory.
    grep -q "pull --ff-only" "$GIT_STUB_LOG"
}

@test "--minimal skips foreground model pull" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    # Ollama 'pull' should NOT have been called.
    if [ -s "$OLLAMA_STUB_LOG" ]; then
        ! grep -q "^pull " "$OLLAMA_STUB_LOG"
    fi
}

@test "install succeeds with no system Python on PATH" {
    # Build a stubs dir with NO python3 / python — verifies the
    # bootstrap shims (get_anon_id, beacon, mark_done) are Python-free.
    local no_py_stubs="$TEST_TMPDIR/no_py_stubs"
    mkdir -p "$no_py_stubs"
    for f in git curl uv ollama cargo rustup; do
        cp "$PER_TEST_STUBS/$f" "$no_py_stubs/"
        chmod +x "$no_py_stubs/$f"
    done
    # Provide minimal core utilities the shims need (od, sed, awk, tr, grep).
    for util in id cat bash sh head tail awk sed grep od tr cut mv rm mkdir cp chmod ln test pgrep date sleep ps; do
        if [[ -x "/usr/bin/$util" ]]; then
            ln -sf "/usr/bin/$util" "$no_py_stubs/$util"
        elif [[ -x "/bin/$util" ]]; then
            ln -sf "/bin/$util" "$no_py_stubs/$util"
        fi
    done
    # pgrep may be absent on minimal BusyBox/Alpine hosts; stub it as
    # "no matching process" so start_ollama's existing-daemon check
    # falls through to the spawn path (which the ollama stub handles).
    if [[ ! -x "$no_py_stubs/pgrep" ]]; then
        printf '#!/bin/sh\nexit 1\n' > "$no_py_stubs/pgrep"
        chmod +x "$no_py_stubs/pgrep"
    fi
    PATH="$no_py_stubs" run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    # State file was still written (mark_done is Python-free).
    [ -f "$NICX_HOME/.state/install-state.json" ]
    # And it still has valid-looking JSON for state_done's grep.
    grep -q '"install_uv":' "$NICX_HOME/.state/install-state.json"
}

@test "mark_done is idempotent — second mark of same key doesn't duplicate" {
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    # Capture first state file
    local first_count
    first_count="$(grep -c '"install_uv":' "$NICX_HOME/.state/install-state.json")"
    [ "$first_count" -eq 1 ]
    # Second run reuses state — keys should not duplicate even if some path re-marks.
    run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    local second_count
    second_count="$(grep -c '"install_uv":' "$NICX_HOME/.state/install-state.json")"
    [ "$second_count" -eq 1 ]
}

@test "create_venv uses the uv-managed Python 3.12 by default" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    grep -q '^venv .*--python 3.12 ' "$UV_STUB_LOG"
}

@test "NICX_PYTHON_VERSION overrides the Python version" {
    NICX_PYTHON_VERSION=3.13 run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    grep -q '^venv .*--python 3.13 ' "$UV_STUB_LOG"
}

@test "dependencies come from the lock file with the server extra" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    grep -q '^sync --frozen --inexact --no-default-groups .*--extra server' "$UV_STUB_LOG"
}

@test "config.toml is created once, local-only and with analytics off" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    grep -q '^default = "ollama"' "$NICX_HOME/config.toml"
    grep -q '^default_model = "qwen3.5:' "$NICX_HOME/config.toml"
    ! grep -qiE 'cloud|api_key' "$NICX_HOME/config.toml"
    echo '# minha linha' >> "$NICX_HOME/config.toml"
    run bash "$SCRIPT" --no-bg-orchestrator --minimal --force
    [ "$status" -eq 0 ]
    grep -q '^# minha linha' "$NICX_HOME/config.toml"
}

@test "NICX_MODEL picks the model written to config.toml" {
    NICX_MODEL=qwen3.5:2b run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    grep -q '^default_model = "qwen3.5:2b"' "$NICX_HOME/config.toml"
}

@test "model download pulls the configured model, and NICX_SKIP_MODEL skips it" {
    NICX_MODEL=qwen3.5:4b run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    grep -q '^pull qwen3.5:4b' "$OLLAMA_STUB_LOG"
    : > "$OLLAMA_STUB_LOG"
    NICX_SKIP_MODEL=1 run bash "$SCRIPT" --no-bg-orchestrator
    [ "$status" -eq 0 ]
    ! grep -q '^pull ' "$OLLAMA_STUB_LOG"
}

@test "PATH line is added once to the shell rc file" {
    SHELL=/bin/zsh run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    [ "$(grep -c '^# Nicx: comandos em ~/.local/bin$' "$FAKE_HOME/.zshrc")" -eq 1 ]
    SHELL=/bin/zsh run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    [ "$(grep -c '^# Nicx: comandos em ~/.local/bin$' "$FAKE_HOME/.zshrc")" -eq 1 ]
}

@test "creates nicx-abrir and nicx-uninstall links" {
    run bash "$SCRIPT" --no-bg-orchestrator --minimal
    [ "$status" -eq 0 ]
    [ -L "$FAKE_HOME/.local/bin/nicx-abrir" ]
    [ -L "$FAKE_HOME/.local/bin/nicx-uninstall" ]
}
