#!/usr/bin/env bash
# pull-model.sh — pull an Ollama model with state-file lifecycle.
#
# Usage: pull-model.sh <model-id>
#
# State files written under $NICX_HOME/.state/models/ (model id URL-encoded):
#   <model>.downloading  — created on start
#   <model>.ready        — on success (atomic rename)
#   <model>.failed       — on failure after retries
#   <model>.log          — captured stderr

set -euo pipefail

MODEL="${1:-}"
if [[ -z "$MODEL" ]]; then
    echo "usage: pull-model.sh <model-id>" >&2
    exit 2
fi

NICX_HOME="${NICX_HOME:-$HOME/.nicx}"
STATE_DIR="$NICX_HOME/.state/models"
mkdir -p "$STATE_DIR"

# ":" (qwen3.5:4b) and "/" (hf.co/x/y) are encoded in file names: on Windows
# ":" opens a hidden NTFS stream and "/" is a folder. Must match
# marker_name() in src/nicx/comandos/instalacao/_bg_state.py.
SAFE="${MODEL//%/%25}"
SAFE="${SAFE//:/%3A}"
SAFE="${SAFE//\//%2F}"
DOWNLOADING="$STATE_DIR/${SAFE}.downloading"
READY="$STATE_DIR/${SAFE}.ready"
FAILED="$STATE_DIR/${SAFE}.failed"
LOG="$STATE_DIR/${SAFE}.log"

# Cleanup any prior state for this model.
rm -f "$READY" "$FAILED"
touch "$DOWNLOADING"

MAX_RETRIES=3
attempt=0
last_exit=0

while [[ $attempt -lt $MAX_RETRIES ]]; do
    attempt=$((attempt + 1))
    if ollama pull "$MODEL" >>"$LOG" 2>&1; then
        # Atomic rename: write to .tmp then mv.
        tmp="$STATE_DIR/${SAFE}.ready.tmp"
        date -u +"%Y-%m-%dT%H:%M:%SZ" > "$tmp"
        mv "$tmp" "$READY"
        rm -f "$DOWNLOADING"
        exit 0
    else
        last_exit=$?
    fi
done

# All retries exhausted.
{
    echo "pull-model.sh: $MODEL failed after $MAX_RETRIES attempts (exit=$last_exit)"
    tail -n 50 "$LOG" 2>/dev/null || true
} > "$FAILED"
rm -f "$DOWNLOADING"
exit "$last_exit"
