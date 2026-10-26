#!/usr/bin/env bats

setup() {
    TEST_TMPDIR=$(mktemp -d)
    export NICX_HOME="$TEST_TMPDIR/.nicx"
    mkdir -p "$NICX_HOME/.state/models"
    mkdir -p "$NICX_HOME/.scripts"
    # Provide mock scripts that all return success and write the expected state files.
    cat > "$NICX_HOME/.scripts/install-rust.sh" <<EOF
#!/usr/bin/env bash
exit 0
EOF
    cat > "$NICX_HOME/.scripts/build-extension.sh" <<EOF
#!/usr/bin/env bash
touch "\$NICX_HOME/.state/extension-built"
exit 0
EOF
    cat > "$NICX_HOME/.scripts/pull-model.sh" <<EOF
#!/usr/bin/env bash
touch "\$NICX_HOME/.state/models/\${1}.ready"
exit 0
EOF
    chmod +x "$NICX_HOME/.scripts/"*.sh
    export SCRIPT="$BATS_TEST_DIRNAME/../../../scripts/install/bg-orchestrator.sh"
}

teardown() {
    [[ -n "${TEST_TMPDIR:-}" ]] && rm -rf "$TEST_TMPDIR"
}

@test "writes pid file" {
    run bash "$SCRIPT" qwen3.5:9b
    [ "$status" -eq 0 ]
    # bg-orchestrator's pid file is removed by the trap on exit.
    # We verify the file existed at SOME point by checking for the log mention.
    [ -f "$NICX_HOME/.state/bg-orchestrator.log" ]
    grep -q "pid=" "$NICX_HOME/.state/bg-orchestrator.log"
}

@test "invokes build-extension after install-rust succeeds" {
    run bash "$SCRIPT" qwen3.5:9b
    [ "$status" -eq 0 ]
    [ -f "$NICX_HOME/.state/extension-built" ]
}

@test "invokes pull-model.sh for each model arg" {
    run bash "$SCRIPT" qwen3.5:9b qwen3.5:27b
    [ "$status" -eq 0 ]
    [ -f "$NICX_HOME/.state/models/qwen3.5:9b.ready" ]
    [ -f "$NICX_HOME/.state/models/qwen3.5:27b.ready" ]
}

@test "removes pid file when done (via trap)" {
    run bash "$SCRIPT" qwen3.5:9b
    [ "$status" -eq 0 ]
    [ ! -f "$NICX_HOME/.state/bg.pid" ]
}
