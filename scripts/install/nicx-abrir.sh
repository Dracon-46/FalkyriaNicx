#!/usr/bin/env bash
# nicx-abrir — liga o servidor do Nicx (se ainda não estiver ligado) e abre
# a interface no navegador. Ligado em ~/.local/bin/nicx-abrir e usado pelo
# app "Nicx" em ~/Applications no macOS.
#
# Uso: nicx-abrir [--sem-navegador]
#   NICX_PORT   porta do servidor (padrão: 8000)

set -u

OPEN_BROWSER=1
for arg in "$@"; do
    case "$arg" in
        --sem-navegador|--no-browser) OPEN_BROWSER=0 ;;
        -h|--help)
            sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "nicx-abrir: opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done

# The wrapper next to this script (both live in ~/.nicx/.scripts).
self="$0"
while [[ -L "$self" ]]; do
    target="$(readlink "$self")"
    case "$target" in
        /*) self="$target" ;;
        *) self="$(dirname "$self")/$target" ;;
    esac
done
NICX_BIN="$(cd "$(dirname "$self")" && pwd -P)/nicx-wrapper.sh"
if [[ ! -x "$NICX_BIN" ]]; then
    NICX_BIN="nicx"
fi

PORT="${NICX_PORT:-8000}"
URL="http://127.0.0.1:$PORT"
LOG_DIR="${NICX_HOME:-$HOME/.nicx}/logs"

# Any HTTP answer means the server is up: /health returns 503 while the
# model engine is down, and the interface itself shows that state.
healthy() {
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "$URL/health" 2>/dev/null)" || true
    [[ -n "$code" && "$code" != "000" ]]
}

notify() {
    echo "$1"
    # Feedback when launched from Finder/Launchpad, where there is no terminal.
    if [[ "$(uname -s 2>/dev/null)" == "Darwin" && ! -t 1 ]]; then
        osascript -e "display notification \"$1\" with title \"Nicx\"" >/dev/null 2>&1 || true
    fi
}

if ! healthy; then
    notify "Ligando o Nicx (a primeira vez pode levar um minuto)..."
    mkdir -p "$LOG_DIR"
    # `nicx start` fails when a server is already registered but still
    # starting; the health wait below covers that case.
    "$NICX_BIN" start --port "$PORT" >>"$LOG_DIR/nicx-abrir.log" 2>&1 || true
    waited=0
    while ! healthy; do
        if (( waited >= 180 )); then
            notify "O Nicx não respondeu em $URL. Rode 'nicx doctor' no Terminal; registro: $LOG_DIR/nicx-abrir.log"
            exit 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
fi

echo "Nicx pronto em $URL"
if [[ "$OPEN_BROWSER" -eq 1 ]]; then
    if command -v open >/dev/null 2>&1; then
        open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 &
    else
        echo "Abra no navegador: $URL"
    fi
fi
