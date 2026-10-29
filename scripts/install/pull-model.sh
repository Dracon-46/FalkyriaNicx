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

# `ollama pull` needs a running server. Start one only if none answers, and
# stop it again at the end: Nicx starts Ollama on demand by itself.
STARTED_PID=""
# shellcheck disable=SC2329 # called by the EXIT trap
stop_started_server() {
    if [[ -n "$STARTED_PID" ]]; then
        kill "$STARTED_PID" 2>/dev/null || true
    fi
}
trap stop_started_server EXIT
if ! curl -fsS --max-time 3 "http://127.0.0.1:11434/api/version" >/dev/null 2>&1; then
    nohup ollama serve >>"$LOG" 2>&1 &
    STARTED_PID=$!
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 \
             21 22 23 24 25 26 27 28 29 30; do
        curl -fsS --max-time 3 "http://127.0.0.1:11434/api/version" >/dev/null 2>&1 && break
        sleep 2
    done
fi

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
