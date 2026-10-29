#!/usr/bin/env bash
# shellcheck disable=SC2329 # step functions are called through step()/check()
# install.sh — instalador do Nicx para macOS e Linux (curl | bash).
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash
#
# Opções (com curl | bash, passe-as depois de `bash -s --`):
#   --non-interactive      Não pergunta nada (CI). Igual a NICX_INSTALL_NONINTERACTIVE=1
#   --minimal              Não baixa o modelo (~3,4 GB). Igual a NICX_SKIP_MODEL=1
#   --voz                  Instala também a voz local (Whisper + Kokoro, ~1,5 GB). NICX_WITH_VOICE=1
#   --servico              Liga o Nicx sozinho ao entrar no macOS (launchd). NICX_LAUNCHD=1
#   --no-bg-orchestrator   Não deixa tarefas em segundo plano (extensão Rust, nova tentativa do modelo)
#   --force                Refaz todas as etapas (e atualiza o código com git pull)
#   --analytics            Aceita as estatísticas anônimas de uso
#   --no-analytics         Recusa as estatísticas sem perguntar
#
# Variáveis:
#   NICX_HOME              Pasta da instalação (padrão: ~/.nicx)
#   NICX_REPO_URL          Repositório git (padrão: https://github.com/Dracon-46/FalkyriaNicx.git)
#   NICX_MODEL             Modelo do Ollama (padrão: qwen3.5:4b; menos RAM escolhe um menor)
#   NICX_PYTHON_VERSION    Python gerenciado pelo uv (padrão: 3.12)
#   NICX_SKIP_OLLAMA=1     Não instala o Ollama (use um já instalado ou remoto)
#   NICX_SKIP_INTERFACE=1  Não compila a interface web
#   NICX_OLLAMA_METHOD     macOS: auto (padrão: brew se houver, senão o app oficial), brew ou download
#   NICX_FORCE_WSL=1       Força a detecção do WSL (testes)
#
# Nada é enviado à Falkyria sem consentimento: as estatísticas começam
# desligadas e só ligam com --analytics ou com "S" na pergunta.

set -euo pipefail

# The whole script is one { ... } block, closed on the last line. With
# `curl | bash`, bash reads the script from stdin as it goes: the block makes
# it parse everything before running anything, so no command can swallow the
# rest of the script from stdin, and a cut-off download runs nothing.
{

is_true() {
    case "${1:-}" in
        1|true|TRUE|True|yes|YES|sim|SIM) return 0 ;;
        *) return 1 ;;
    esac
}

# ---- args ----
SKIP_BG=0
FORCE=0
ANALYTICS_ENABLED=0
ANALYTICS_CHOICE=""
NONINTERACTIVE=0
SKIP_MODEL=0
WITH_VOICE=0
WANT_LAUNCHD=0
is_true "${NICX_INSTALL_NONINTERACTIVE:-}" && NONINTERACTIVE=1
is_true "${NICX_SKIP_MODEL:-}" && SKIP_MODEL=1
is_true "${NICX_WITH_VOICE:-}" && WITH_VOICE=1
is_true "${NICX_LAUNCHD:-}" && WANT_LAUNCHD=1
for arg in "$@"; do
    case "$arg" in
        --no-bg-orchestrator) SKIP_BG=1 ;;
        --minimal|--sem-modelo) SKIP_MODEL=1 ;;
        --non-interactive|--nao-interativo) NONINTERACTIVE=1 ;;
        --voz) WITH_VOICE=1 ;;
        --servico) WANT_LAUNCHD=1 ;;
        --force) FORCE=1 ;;
        --analytics|--no-analytics)
            if [[ -n "$ANALYTICS_CHOICE" && "$ANALYTICS_CHOICE" != "$arg" ]]; then
                echo "install.sh: --analytics e --no-analytics não podem ser usados juntos" >&2
                exit 2
            fi
            ANALYTICS_CHOICE="$arg"
            ;;
        *) echo "install.sh: opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done
SKIP_OLLAMA=0
SKIP_INTERFACE=0
is_true "${NICX_SKIP_OLLAMA:-}" && SKIP_OLLAMA=1
is_true "${NICX_SKIP_INTERFACE:-}" && SKIP_INTERFACE=1
OLLAMA_METHOD="${NICX_OLLAMA_METHOD:-auto}"
PYTHON_VERSION="${NICX_PYTHON_VERSION:-3.12}"

# `uname` may be missing on stripped-down hosts (and in the tests); never
# let that abort the install under `set -e`.
OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
ARCH_NAME="$(uname -m 2>/dev/null || echo unknown)"

# ---- non-WSL Windows refusal ----
# Git Bash / MSYS2 / Cygwin on native Windows would install into paths the
# rest of Nicx can't reach. Windows has its own installer.
case "$OS_NAME" in
    MINGW*|MSYS*|CYGWIN*)
        cat >&2 <<'EOF'
install.sh: este instalador é para macOS e Linux.

No Windows, use o instalador próprio do Nicx ou, para a linha de comando,
o WSL2 (Ubuntu) e rode este mesmo comando dentro dele.
EOF
        exit 1
        ;;
esac

# ---- root refusal ----
if [[ "$(id -u)" -eq 0 ]]; then
    cat >&2 <<'EOF'
install.sh: não rode como root (nem com sudo).

O Nicx se instala em $HOME/.nicx e não precisa de administrador. Rode de
novo com o seu usuário normal.
EOF
    exit 1
fi

info() { printf '    %s\n' "$*"; }
warn() { printf '    aviso: %s\n' "$*" >&2; }

# Homebrew is optional. Find it even when this non-login shell did not load
# `brew shellenv` (Apple Silicon installs live in /opt/homebrew).
BREW=""
if command -v brew >/dev/null 2>&1; then
    BREW="$(command -v brew)"
elif [[ -x /opt/homebrew/bin/brew ]]; then
    BREW=/opt/homebrew/bin/brew
elif [[ -x /usr/local/bin/brew ]]; then
    BREW=/usr/local/bin/brew
fi

# PATH before we touch it: ensure_path must look at what the user's shell
# really has, not at the entries added below for this run.
ORIG_PATH="$PATH"
export PATH="$HOME/.local/bin:$PATH"
if [[ -n "$BREW" ]]; then
    case ":$PATH:" in
        *":${BREW%/brew}:"*) ;;
        *) export PATH="$PATH:${BREW%/brew}" ;;
    esac
fi

# ---- prereq probe ----
#
# `git` and `curl` are the only host tools we require. On macOS curl ships
# with the system and git comes with the Xcode Command Line Tools.
need() {
    local tool="$1"
    if [[ "$OS_NAME" == "Darwin" && "$tool" == "git" ]]; then
        macos_git_ready && return 0
        bootstrap_macos_clt
        return 0
    fi
    if command -v "$tool" >/dev/null 2>&1; then
        return 0
    fi
    case "$OS_NAME" in
        Darwin)  bootstrap_macos_clt ;;
        Linux)   bootstrap_linux_tool "$tool" ;;
        *)       fail_missing_tool "$tool" ;;
    esac
}

macos_git_ready() {
    command -v git >/dev/null 2>&1 || return 1
    # /usr/bin/git is only a shim until the Command Line Tools are installed:
    # running it opens the install dialog and fails.
    if [[ "$(command -v git)" == "/usr/bin/git" ]]; then
        xcode-select -p >/dev/null 2>&1 || return 1
    fi
    return 0
}

bootstrap_macos_clt() {
    if [[ "$NONINTERACTIVE" -eq 1 || -n "${SSH_CONNECTION:-}${SSH_TTY:-}" ]]; then
        cat >&2 <<'EOF'
install.sh: o git não está instalado. Ele vem com as Ferramentas de Linha de
Comando do Xcode, que precisam de uma sessão com tela:

  xcode-select --install

Depois rode o instalador de novo.
EOF
        exit 1
    fi
    echo "install.sh: instalando as Ferramentas de Linha de Comando do Xcode (trazem o git)..."
    echo "  Uma janela do sistema vai abrir: clique em 'Instalar' e aceite a licença."
    xcode-select --install 2>/dev/null || true
    local waited=0
    while ! { xcode-select -p >/dev/null 2>&1 && git --version >/dev/null 2>&1; }; do
        if (( waited >= 1800 )); then  # 30 minutes: the download is large
            echo "install.sh: as Ferramentas de Linha de Comando não terminaram de instalar." >&2
            echo "  Termine pela janela do sistema e rode este comando de novo." >&2
            exit 1
        fi
        sleep 5
        waited=$((waited + 5))
        if (( waited % 60 == 0 )); then
            echo "  …aguardando as Ferramentas de Linha de Comando (${waited}s)"
        fi
    done
    echo "  git instalado."
}

bootstrap_linux_tool() {
    local tool="$1"
    # We need passwordless sudo (or already-root) — stdin is the curl
    # pipe, so an interactive password prompt will either hang or fail.
    if [[ "$(id -u)" -ne 0 ]] && ! sudo -n true 2>/dev/null; then
        cat >&2 <<EOF
install.sh: '$tool' não está instalado e instalá-lo pelo gerenciador de
pacotes exige sudo, que pediria uma senha (o terminal está ocupado pelo curl).

  1. Instale '$tool' e rode o instalador de novo:
       Debian/Ubuntu: sudo apt install -y $tool
       Fedora/RHEL:   sudo dnf install -y $tool
       Arch:          sudo pacman -S $tool

  2. Ou autentique o sudo antes (vale por 5 min):
       sudo -v && curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash
EOF
        exit 1
    fi
    local sudo=""
    [[ "$(id -u)" -ne 0 ]] && sudo="sudo"
    echo "install.sh: '$tool' não encontrado; instalando pelo gerenciador de pacotes..."
    if command -v apt-get >/dev/null 2>&1; then
        $sudo apt-get update -q || true
        $sudo apt-get install -y "$tool"
    elif command -v dnf >/dev/null 2>&1; then
        $sudo dnf install -y "$tool"
    elif command -v yum >/dev/null 2>&1; then
        $sudo yum install -y "$tool"
    elif command -v pacman >/dev/null 2>&1; then
        $sudo pacman -S --noconfirm "$tool"
    elif command -v zypper >/dev/null 2>&1; then
        $sudo zypper install -y "$tool"
    elif command -v apk >/dev/null 2>&1; then
        $sudo apk add --no-cache "$tool"
    else
        fail_missing_tool "$tool"
    fi
    if ! command -v "$tool" >/dev/null 2>&1; then
        fail_missing_tool "$tool"
    fi
}

fail_missing_tool() {
    cat >&2 <<EOF
install.sh: '$1' é necessário e não foi possível instalá-lo sozinho.

Como instalar:
  macOS:         xcode-select --install (traz o git)
  Debian/Ubuntu: sudo apt install $1
  Fedora/RHEL:   sudo dnf install $1
  Arch:          sudo pacman -S $1

Depois rode este instalador de novo.
EOF
    exit 1
}

need git
need curl

# ---- env ----
# Nicx keeps ALL of its state under a single root. Relocate it by exporting
# NICX_HOME before running the installer. The Python runtime honors the
# same override (and, when NICX_HOME is unset, $XDG_DATA_HOME/nicx).
NICX_HOME="${NICX_HOME:-$HOME/.nicx}"
NICX_REPO_URL="${NICX_REPO_URL:-https://github.com/Dracon-46/FalkyriaNicx.git}"
SRC_DIR="$NICX_HOME/src"
VENV_DIR="$NICX_HOME/.venv"
STATE_DIR="$NICX_HOME/.state"
SCRIPTS_DIR="$NICX_HOME/.scripts"
TOOLS_DIR="$NICX_HOME/.tools"
STATE_FILE="$STATE_DIR/install-state.json"
LAUNCHD_LABEL="br.com.falkyria.nicx"
MAC_LAUNCHER="$HOME/Applications/Nicx.app"
OLLAMA_URL="http://127.0.0.1:11434"

mkdir -p "$NICX_HOME" "$STATE_DIR" "$SCRIPTS_DIR"

# ---- WSL detection ----
WSL=0
if [[ "${NICX_FORCE_WSL:-0}" == "1" ]]; then
    WSL=1
elif [[ -f /proc/sys/kernel/osrelease ]] && grep -qi "microsoft" /proc/sys/kernel/osrelease 2>/dev/null; then
    WSL=1
fi

# ---- analytics consent and install beacons ----
#
# With consent only, posts a small JSON event to Falkyria's Supabase at each
# install stage so the team can see where installs fail. Payloads contain
# OS, arch, elapsed time, stage name and a random installation ID — never
# names, paths or content. The publishable key is public by design: row
# level security only lets it insert events.
ANALYTICS_HOST="${NICX_ANALYTICS_HOST-https://xcazupxhoeoogcksymzg.supabase.co}"
ANALYTICS_KEY="${NICX_ANALYTICS_KEY-sb_publishable_udh4J44z3XxDaXlGTYbaIA_iT9NcTQD}"
ANON_ID_FILE="$NICX_HOME/anon_id"
INSTALL_START_EPOCH="$(date +%s)"
CURRENT_STAGE=""

analytics_enabled() {
    [[ "$ANALYTICS_ENABLED" -eq 1 && -n "$ANALYTICS_HOST" && -n "$ANALYTICS_KEY" ]]
}

choose_analytics() {
    if [[ -z "$ANALYTICS_HOST" || -z "$ANALYTICS_KEY" ]]; then
        return
    fi
    case "$ANALYTICS_CHOICE" in
        --analytics) ANALYTICS_ENABLED=1; return ;;
        --no-analytics) return ;;
    esac
    if [[ "$NONINTERACTIVE" -eq 1 ]]; then
        echo "Estatísticas desligadas (modo não interativo). Para aceitar: --analytics." >&2
        return
    fi
    # The usual curl | bash entry point occupies stdin. Read a real
    # controlling terminal instead; EOF/unattended runs never consent.
    if [[ ! -t 2 ]] || ! { exec 3<> /dev/tty; } 2>/dev/null; then
        echo "Estatísticas desligadas (sem terminal interativo). Para aceitar: --analytics." >&2
        return
    fi

    cat >&3 <<'EOF'

Ajude a melhorar o Nicx

Com a sua permissão, o Nicx envia à Falkyria estatísticas anônimas de uso:
quais recursos você usa, tempos de resposta, contagem de tokens, tipos de erro,
versão e sistema operacional, ligados a um código aleatório desta instalação.

Nunca enviamos suas conversas, arquivos, nome ou e-mail. Os dados ficam em
servidores no Brasil e são apagados após 24 meses.

É opcional: recusar não muda nada no Nicx. Sem resposta, fica desligado e o
aplicativo pergunta de novo depois. Para mudar quando quiser:
nicx config set analytics.enabled false
Política de privacidade completa: nicx legal privacidade
EOF
    printf 'Destino dos dados: %s\n' "$ANALYTICS_HOST" >&3
    local answer
    while true; do
        printf 'Digite S para aceitar ou N para recusar (Enter: decidir depois): ' >&3
        if ! IFS= read -r answer <&3; then
            printf '\nEstatísticas desligadas (nenhuma resposta).\n' >&3
            break
        fi
        case "$answer" in
            "")
                printf 'Estatísticas desligadas por enquanto; o aplicativo pergunta de novo.\n' >&3
                break
                ;;
            s|S|sim|SIM|Sim|y|Y|yes|YES|Yes)
                ANALYTICS_ENABLED=1
                ANALYTICS_CHOICE="--analytics"
                break
                ;;
            n|N|nao|NAO|Nao|não|Não|NÃO|no|NO|No) ANALYTICS_CHOICE="--no-analytics"; break ;;
            *) printf 'Digite S, N ou só Enter.\n' >&3 ;;
        esac
    done
    exec 3>&-
}

persist_analytics_choice() {
    # Always run, including when the installer skips write_config on a
    # rerun. Use the installed TOML editor directly: an older nicx CLI
    # rejects the new choice_recorded key before it can save the choice.
    local enabled=false
    if analytics_enabled; then
        enabled=true
    fi
    "$VENV_DIR/bin/python" - "$enabled" "$ANALYTICS_CHOICE" <<'PYEOF'
import os
import sys
import tempfile
from pathlib import Path

import tomlkit

from nicx.nucleo.config import DEFAULT_CONFIG_PATH

path = Path(os.environ.get("NICX_CONFIG") or DEFAULT_CONFIG_PATH).expanduser().resolve()
path.parent.mkdir(parents=True, exist_ok=True)
doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
if "analytics" not in doc:
    doc.add("analytics", tomlkit.table())
doc["analytics"]["enabled"] = sys.argv[1] == "true"
if sys.argv[2]:
    doc["analytics"]["choice_recorded"] = True

temporary = None
try:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(tomlkit.dumps(doc))
    temporary.replace(path)
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
PYEOF
}

detect_os() {
    case "$OS_NAME" in
        Darwin) echo "darwin" ;;
        Linux) [[ "$WSL" -eq 1 ]] && echo "wsl" || echo "linux" ;;
        *) echo "unknown" ;;
    esac
}

detect_arch() {
    case "$ARCH_NAME" in
        x86_64|amd64) echo "x86_64" ;;
        arm64|aarch64) echo "arm64" ;;
        *) echo "unknown" ;;
    esac
}

get_anon_id() {
    # POSIX shell UUID v4 — no Python required.
    if [[ -f "$ANON_ID_FILE" ]]; then
        cat "$ANON_ID_FILE"
        return
    fi
    local raw new_id
    raw="$(od -An -tx1 -N16 /dev/urandom 2>/dev/null | tr -d ' \n')" || true
    if [[ ${#raw} -ne 32 ]]; then
        return 0  # /dev/urandom unreadable — skip analytics silently
    fi
    new_id="${raw:0:8}-${raw:8:4}-${raw:12:4}-${raw:16:4}-${raw:20:12}"
    echo "$new_id" > "$ANON_ID_FILE"
    echo "$new_id"
}

stage_label() {
    # Only labels the database check constraint accepts.
    case "$1" in
        install_uv) echo "uv" ;;
        clone_repo|copy_scripts) echo "deps" ;;
        create_venv) echo "venv" ;;
        editable_install|build_interface) echo "package" ;;
        install_ollama) echo "ollama" ;;
        pull_default_model) echo "model_download" ;;
        write_config) echo "config" ;;
        install_symlinks|ensure_path|install_launchd|detach_bg_orchestrator) echo "verify" ;;
        *) echo "" ;;
    esac
}

beacon() {
    # Args: event_name stage_label elapsed_ms exit_code
    #
    # No Python required — uses curl + shell-built JSON. All inputs come
    # from controlled sources (fixed event names, stage_label(), numbers,
    # a fresh UUID), so no general-purpose JSON escaping is needed.
    local event="$1"
    local stage="${2:-}"
    local elapsed_ms="${3:-0}"
    local exit_code="${4:-0}"

    if ! analytics_enabled; then
        return 0
    fi

    local anon_id os arch
    anon_id="$(get_anon_id)"
    if [[ -z "$anon_id" ]]; then
        return 0
    fi
    os="$(detect_os)"
    arch="$(detect_arch)"

    local props
    props='"os":"'"$os"'","arch":"'"$arch"'","installer_version":"0.2.0"'
    if [[ -n "$stage" ]]; then
        props="${props},\"stage\":\"$stage\""
    fi
    if [[ "$event" = "install_completed" ]]; then
        props="${props},\"total_elapsed_ms\":${elapsed_ms}"
    elif [[ "$elapsed_ms" != "0" ]]; then
        props="${props},\"elapsed_ms\":${elapsed_ms}"
    fi
    if [[ "$exit_code" != "0" ]]; then
        props="${props},\"exit_code\":${exit_code}"
    fi

    local payload
    payload="{\"anon_id\":\"$anon_id\",\"event\":\"$event\",\"properties\":{$props},\"platform\":\"installer\",\"os\":\"$os\",\"arch\":\"$arch\",\"app_version\":\"installer-0.2.0\"}"

    # Legacy anon keys are JWTs and also go in the bearer header; the newer
    # sb_publishable_ keys must not. The `${auth[@]+...}` form keeps an
    # empty array from tripping `set -u` on the macOS bash 3.2.
    local auth=()
    if [[ "$ANALYTICS_KEY" == eyJ* ]]; then
        auth=(-H "Authorization: Bearer $ANALYTICS_KEY")
    fi

    # Fire and forget: a flaky analytics post must never abort an install.
    curl -s -X POST \
        -H 'Content-Type: application/json' \
        -H "apikey: $ANALYTICS_KEY" \
        -H 'Prefer: return=minimal' \
        ${auth[@]+"${auth[@]}"} \
        -d "$payload" \
        --max-time 5 \
        "${ANALYTICS_HOST}/rest/v1/nicx_events" \
        >/dev/null 2>&1 || true
}

_on_install_error() {
    local exit_code=$?
    beacon "install_failed" "$(stage_label "$CURRENT_STAGE")" 0 "$exit_code"
    echo >&2
    echo "A instalação parou na etapa '$CURRENT_STAGE' (código $exit_code)." >&2
    echo "Corrija o problema acima e rode o mesmo comando de novo: as etapas prontas são puladas." >&2
    exit "$exit_code"
}
trap _on_install_error ERR

# ---- helpers ----
state_done() {
    [[ -f "$STATE_FILE" ]] && grep -q "\"$1\":[[:space:]]*true" "$STATE_FILE"
}

mark_done() {
    # Shell-only state-file update so the install never needs python3.
    # Format: a flat JSON object of `"<step_name>": true` lines plus a
    # `"wsl": true|false` trailer. nicx-uninstall.sh reads it as proof
    # that this directory belongs to Nicx.
    local key="$1"
    if [[ ! -f "$STATE_FILE" ]] || [[ ! -s "$STATE_FILE" ]]; then
        echo '{}' > "$STATE_FILE"
    fi

    if grep -q "\"$key\":[[:space:]]*true" "$STATE_FILE"; then
        return 0
    fi

    local wsl_bool
    wsl_bool="$([[ $WSL -eq 1 ]] && echo true || echo false)"

    local tmp="${STATE_FILE}.tmp.$$"
    awk -v new_key="$key" -v wsl="$wsl_bool" '
    /"[^"]+":[[:space:]]*true/ {
        match($0, /"[^"]+"/)
        k = substr($0, RSTART + 1, RLENGTH - 2)
        if (k != "wsl") keys[++n] = k
    }
    END {
        keys[++n] = new_key
        print "{"
        for (i = 1; i <= n; i++) {
            printf "  \"%s\": true,\n", keys[i]
        }
        printf "  \"wsl\": %s\n", wsl
        print "}"
    }
    ' "$STATE_FILE" > "$tmp"
    mv "$tmp" "$STATE_FILE"
}

# step: runs once; later runs skip it (unless --force).
step() {
    local name="$1" desc="$2"; shift 2
    CURRENT_STAGE="$name"
    if [[ "$FORCE" -ne 1 ]] && state_done "$name"; then
        echo "[ok] $desc (já feito)"
        return 0
    fi
    echo "[..] $desc"
    local stage_start_epoch stage_elapsed_ms
    stage_start_epoch="$(date +%s)"
    "$@"
    mark_done "$name"
    stage_elapsed_ms=$(( ( $(date +%s) - stage_start_epoch ) * 1000 ))
    beacon "install_stage_completed" "$(stage_label "$name")" "$stage_elapsed_ms"
    echo "[ok] $desc"
}

# check: runs every time; the function itself decides what is missing.
check() {
    local name="$1" desc="$2"; shift 2
    CURRENT_STAGE="$name"
    echo "[..] $desc"
    local stage_start_epoch stage_elapsed_ms
    stage_start_epoch="$(date +%s)"
    "$@"
    stage_elapsed_ms=$(( ( $(date +%s) - stage_start_epoch ) * 1000 ))
    beacon "install_stage_completed" "$(stage_label "$name")" "$stage_elapsed_ms"
    echo "[ok] $desc"
}

sha256_of() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        return 1
    fi
}

# version_ge A B: true when version A >= B (numeric, up to 3 parts).
version_ge() {
    local -a a b
    IFS=. read -r -a a <<< "$1"
    IFS=. read -r -a b <<< "$2"
    local i x y
    for i in 0 1 2; do
        x="${a[i]:-0}"; y="${b[i]:-0}"
        x="${x%%[!0-9]*}"; y="${y%%[!0-9]*}"
        x="${x:-0}"; y="${y:-0}"
        if (( 10#$x > 10#$y )); then return 0; fi
        if (( 10#$x < 10#$y )); then return 1; fi
    done
    return 0
}

# Total RAM in MB (0 when unknown).
ram_mb() {
    local bytes kb
    case "$OS_NAME" in
        Darwin)
            bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
            case "$bytes" in ''|*[!0-9]*) bytes=0 ;; esac
            echo $(( bytes / 1048576 ))
            ;;
        *)
            kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
            case "$kb" in ''|*[!0-9]*) kb=0 ;; esac
            echo $(( kb / 1024 ))
            ;;
    esac
}

macos_preflight() {
    local ver major translated mem
    ver="$(sw_vers -productVersion 2>/dev/null || echo 0)"
    major="${ver%%.*}"
    case "$major" in ''|*[!0-9]*) major=0 ;; esac
    echo "  macOS:       $ver ($ARCH_NAME)"
    if (( major > 0 && major < 14 )); then
        warn "o Ollama pede macOS 14 (Sonoma) ou mais novo. O Nicx se instala, mas o modelo local pode não rodar neste Mac."
    fi
    translated="$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)"
    if [[ "$translated" == "1" ]]; then
        warn "este Terminal está rodando pelo Rosetta (modo Intel) num Mac Apple Silicon: tudo ficaria mais lento. Feche-o, desmarque 'Abrir com Rosetta' no Terminal e rode o comando de novo."
    elif [[ "$ARCH_NAME" == "x86_64" ]]; then
        info "Mac Intel: o modelo roda só no processador (as respostas demoram mais)."
    fi
    mem="$(ram_mb)"
    if (( mem > 0 && mem < 8000 )); then
        warn "este Mac tem menos de 8 GB de RAM; o Nicx vai usar um modelo menor."
    fi
}

# ---- step impls ----
install_uv() {
    if command -v uv >/dev/null 2>&1; then
        info "uv já instalado"
        return 0
    fi
    # Our own ensure_path adds ~/.local/bin; keep uv's installer away from
    # the shell rc files.
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "install.sh: o uv foi instalado, mas não aparece em $HOME/.local/bin" >&2
        return 1
    fi
}

clone_repo() {
    if [[ -d "$SRC_DIR/.git" ]]; then
        if [[ "$FORCE" -ne 1 ]]; then
            echo "    repo already at $SRC_DIR"
            return 0
        fi
        # --force on an existing install: update the code instead of a
        # re-clone, which git refuses into a non-empty directory.
        git -C "$SRC_DIR" pull --ff-only
        return 0
    fi
    # Keep commit/tag history for hatch-vcs. Local sources may themselves be
    # shallow and cannot safely serve a partial clone's lazy object fetches.
    if [[ "$NICX_REPO_URL" == file://* || -e "$NICX_REPO_URL" ]]; then
        git clone "$NICX_REPO_URL" "$SRC_DIR"
    else
        git clone --filter=blob:none "$NICX_REPO_URL" "$SRC_DIR"
    fi
}

copy_scripts() {
    cp -f "$SRC_DIR"/scripts/install/*.sh "$SCRIPTS_DIR/"
    chmod +x "$SCRIPTS_DIR"/*.sh
}

create_venv() {
    # Python 3.12 managed by uv (the version Nicx is developed and tested
    # with). only-managed keeps a Homebrew/system Python out of the venv: a
    # `brew upgrade python` would otherwise break it later.
    echo "    Python $PYTHON_VERSION (gerenciado pelo uv)"
    local err_log="$STATE_DIR/venv-create.err"
    if ! UV_PYTHON_PREFERENCE=only-managed uv venv --allow-existing --python "$PYTHON_VERSION" "$VENV_DIR" 2>"$err_log"; then
        echo "    baixando o Python $PYTHON_VERSION..."
        uv python install "$PYTHON_VERSION"
        if ! UV_PYTHON_PREFERENCE=only-managed uv venv --allow-existing --python "$PYTHON_VERSION" "$VENV_DIR"; then
            echo "    não foi possível criar o ambiente Python. Erro da primeira tentativa:" >&2
            sed 's/^/      /' "$err_log" >&2
            return 1
        fi
    fi
    rm -f "$err_log"
}

editable_install() {
    # The lock file pins every dependency to what is tested. --inexact
    # keeps the Rust extension that build-extension.sh adds later.
    local extras=(server memory-bm25 pdf)
    if [[ "$WITH_VOICE" -eq 1 ]]; then
        extras+=(speech voice)
    fi
    local sync_args=() e
    for e in "${extras[@]}"; do
        sync_args+=(--extra "$e")
    done
    cd "$SRC_DIR"
    if UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync --frozen --inexact --no-default-groups "${sync_args[@]}"; then
        return 0
    fi
    warn "uv sync falhou; tentando instalar sem o arquivo de versões travadas..."
    local joined
    joined="$(IFS=,; echo "${extras[*]}")"
    uv pip install --python "$VENV_DIR/bin/python" -e ".[$joined]"
}

# ---- interface (frontend) ----
NODE_DIR="$TOOLS_DIR/node"
INTERFACE_OK=1

# A Node/npm pair that satisfies frontend/package.json (engine-strict):
# node >= 22.22 and npm 11.x >= 11.19.
node_dir_ok() {
    local dir="$1" v npmv
    [[ -x "$dir/node" && -x "$dir/npm" ]] || return 1
    v="$("$dir/node" -v 2>/dev/null)" || return 1
    npmv="$(PATH="$dir:$PATH" "$dir/npm" -v 2>/dev/null)" || return 1
    version_ge "${v#v}" 22.22.0 || return 1
    version_ge "$npmv" 11.19.0 || return 1
    [[ "${npmv%%.*}" == "11" ]]
}

install_private_node() {
    # Official Node.js 24 LTS build, checked against nodejs.org's SHA-256
    # list, unpacked under ~/.nicx/.tools (no admin, removed on uninstall).
    local os arch base sums line sha file tmp
    case "$OS_NAME" in
        Darwin) os=darwin ;;
        Linux) os=linux ;;
        *) return 1 ;;
    esac
    case "$ARCH_NAME" in
        arm64|aarch64) arch=arm64 ;;
        x86_64|amd64) arch=x64 ;;
        *) return 1 ;;
    esac
    base="https://nodejs.org/dist/latest-v24.x"
    sums="$(curl -fsSL "$base/SHASUMS256.txt")" || return 1
    line="$(printf '%s\n' "$sums" | grep -E "  node-v[0-9.]+-$os-$arch\.tar\.gz\$" | head -1)"
    [[ -n "$line" ]] || return 1
    sha="${line%% *}"
    file="${line##* }"
    tmp="$(mktemp -d)"
    info "baixando $file (só para compilar a interface)..."
    if ! curl -fsSL -o "$tmp/$file" "$base/$file"; then
        rm -rf "$tmp"
        return 1
    fi
    if [[ "$(sha256_of "$tmp/$file")" != "$sha" ]]; then
        warn "o arquivo do Node.js não confere com o SHA-256 oficial; descartado."
        rm -rf "$tmp"
        return 1
    fi
    rm -rf "$NODE_DIR"
    mkdir -p "$NODE_DIR"
    tar -xzf "$tmp/$file" -C "$NODE_DIR" --strip-components 1
    rm -rf "$tmp"
}

find_node_dir() {
    local sys_node
    if sys_node="$(command -v node 2>/dev/null)" && node_dir_ok "${sys_node%/node}"; then
        echo "${sys_node%/node}"
        return 0
    fi
    if node_dir_ok "$NODE_DIR/bin"; then
        echo "$NODE_DIR/bin"
        return 0
    fi
    install_private_node >&2 || return 1
    node_dir_ok "$NODE_DIR/bin" || return 1
    echo "$NODE_DIR/bin"
}

build_interface() {
    local fe="$SRC_DIR/frontend"
    local index="$SRC_DIR/src/nicx/servidor/static/index.html"
    if [[ "$SKIP_INTERFACE" -eq 1 ]]; then
        info "pulado (NICX_SKIP_INTERFACE)"
        INTERFACE_OK=0
        return 0
    fi
    if [[ ! -f "$fe/package.json" ]]; then
        info "o código baixado não tem a interface; pulando"
        INTERFACE_OK=0
        return 0
    fi
    if [[ -f "$index" && "$FORCE" -ne 1 ]]; then
        info "interface já compilada"
        return 0
    fi
    local node_bin log="$STATE_DIR/interface-build.log"
    if ! node_bin="$(find_node_dir)"; then
        warn "não foi possível obter o Node.js 24; a interface web fica para depois (o 'nicx chat' funciona)."
        INTERFACE_OK=0
        return 0
    fi
    info "compilando a interface (alguns minutos)..."
    if ! (cd "$fe" && export PATH="$node_bin:$PATH" \
            && npm ci --no-audit --no-fund && npm run build) >"$log" 2>&1; then
        warn "a compilação da interface falhou; veja $log"
        tail -n 25 "$log" >&2 || true
        INTERFACE_OK=0
        return 0
    fi
    # ~600 MB that only the build needs.
    rm -rf "$fe/node_modules"
    if [[ ! -f "$index" ]]; then
        warn "a compilação terminou sem gerar $index"
        INTERFACE_OK=0
    fi
}

# ---- configuration ----
CHOSEN_MODEL=""
NUM_CTX=8192

choose_model() {
    # Same rule as the Windows installer.
    local mem
    mem="$(ram_mb)"
    if [[ -n "${NICX_MODEL:-}" ]]; then
        CHOSEN_MODEL="$NICX_MODEL"
        if (( mem > 0 && mem < 12000 )); then NUM_CTX=4096; fi
    elif (( mem > 0 && mem < 4000 )); then
        CHOSEN_MODEL="qwen3.5:0.8b"; NUM_CTX=2048
    elif (( mem > 0 && mem < 8000 )); then
        CHOSEN_MODEL="qwen3.5:2b"; NUM_CTX=4096
    elif (( mem > 0 && mem < 12000 )); then
        CHOSEN_MODEL="qwen3.5:4b"; NUM_CTX=4096
    else
        CHOSEN_MODEL="qwen3.5:4b"
    fi
}

write_config() {
    # Creates config.toml only when it does not exist yet (an existing one
    # is never touched), then seeds SOUL.md / MEMORY.md / USER.md.
    "$VENV_DIR/bin/python" - "$CHOSEN_MODEL" "$NUM_CTX" "$(ram_mb)" <<'PYEOF'
import os
import sys
from datetime import date
from pathlib import Path

from nicx.nucleo.config import DEFAULT_CONFIG_PATH

model, num_ctx, ram_mb = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
path = Path(os.environ.get("NICX_CONFIG") or DEFAULT_CONFIG_PATH).expanduser()
if path.exists():
    print(f"    configuração existente mantida: {path}")
else:
    path.parent.mkdir(parents=True, exist_ok=True)
    ram = f"{ram_mb / 1024:.1f} GB de RAM" if ram_mb else "RAM desconhecida"
    path.write_text(
        f"""# Configuração do Nicx (criada pelo instalador em {date.today().isoformat()})
# Computador: {ram}
# Referência completa: nicx init --full

[engine]
default = "ollama"

[engine.ollama]
# host = "http://localhost:11434"
# Janela de contexto (tokens). Menor = menos memória. Se o Ollama acusar falta
# de memória, use 4096.
num_ctx = {num_ctx}

[intelligence]
default_model = "{model}"

[agent]
default_agent = "simple"

[tools]
enabled = ["code_interpreter", "web_search", "file_read", "shell_exec"]

[security]
profile = "personal"

[analytics]
# Desligado até você decidir (aqui no instalador ou em Configurações > Privacidade).
enabled = false

[speech]
# Voz em português do Brasil, tudo local (instale com: install.sh --voz).
backend = "faster-whisper"
model = "base"
language = "pt"
device = "cpu"
compute_type = "int8"
vad_filter = true
hotwords = "Nicx Falkyria"
tts_backend = "kokoro"
voice_id = "pf_dora"
voice_speed = 1.0
""",
        encoding="utf-8",
    )
    print(f"    configuração criada: {path}")

try:
    from nicx.comandos.instalacao._bootstrap import _seed_memory_files
except Exception:
    print("    (SOUL.md/MEMORY.md/USER.md ficam para o primeiro uso)")
else:
    _seed_memory_files()
PYEOF
}

config_model() {
    # The model the installed config asks for (falls back to CHOSEN_MODEL).
    "$VENV_DIR/bin/python" - "$CHOSEN_MODEL" 2>/dev/null <<'PYEOF' || echo "$CHOSEN_MODEL"
import os
import sys
from pathlib import Path

import tomlkit

from nicx.nucleo.config import DEFAULT_CONFIG_PATH

path = Path(os.environ.get("NICX_CONFIG") or DEFAULT_CONFIG_PATH).expanduser()
model = ""
if path.exists():
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    engine = str(doc.get("engine", {}).get("default", "ollama"))
    if engine == "ollama":
        model = str(doc.get("intelligence", {}).get("default_model", "") or "")
    else:
        model = "-"
print(model or sys.argv[1])
PYEOF
}

# ---- Ollama ----
OLLAMA_APP=""

ollama_up() {
    curl -fsS --max-time 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1
}

find_ollama_app() {
    local candidate
    for candidate in "/Applications/Ollama.app" "$HOME/Applications/Ollama.app"; do
        if [[ -x "$candidate/Contents/Resources/ollama" ]]; then
            OLLAMA_APP="$candidate"
            return 0
        fi
    done
    return 1
}

download_ollama_app() {
    # Official release from github.com/ollama/ollama, checked against the
    # release's sha256sum.txt and Apple's code signature.
    local latest tag base tmp expected actual dest_dir
    latest="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/ollama/ollama/releases/latest)" || return 1
    tag="${latest##*/}"
    if [[ "$tag" != v* ]]; then
        warn "não foi possível descobrir a versão atual do Ollama"
        return 1
    fi
    base="https://github.com/ollama/ollama/releases/download/$tag"
    tmp="$(mktemp -d)"
    info "baixando o Ollama $tag (app oficial)..."
    if ! curl -fL --progress-bar -o "$tmp/Ollama-darwin.zip" "$base/Ollama-darwin.zip"; then
        rm -rf "$tmp"
        return 1
    fi
    expected="$(curl -fsSL "$base/sha256sum.txt" | awk '$2 == "./Ollama-darwin.zip" || $2 == "Ollama-darwin.zip" {print $1}')" || true
    actual="$(sha256_of "$tmp/Ollama-darwin.zip")" || true
    if [[ -z "$expected" || "$actual" != "$expected" ]]; then
        warn "o download do Ollama não confere com o SHA-256 publicado; descartado."
        rm -rf "$tmp"
        return 1
    fi
    # (Runs under `|| OLLAMA_OK=0`, where set -e is off: check every step.)
    ditto -x -k "$tmp/Ollama-darwin.zip" "$tmp/app" || true
    if [[ ! -x "$tmp/app/Ollama.app/Contents/Resources/ollama" ]]; then
        warn "o pacote do Ollama veio sem o programa esperado."
        rm -rf "$tmp"
        return 1
    fi
    if ! codesign --verify --deep --strict "$tmp/app/Ollama.app" 2>/dev/null; then
        warn "a assinatura do Ollama.app não é válida; descartado."
        rm -rf "$tmp"
        return 1
    fi
    # /Applications when the user can write there without sudo (admin
    # accounts); otherwise ~/Applications.
    dest_dir="/Applications"
    if [[ ! -w "$dest_dir" ]]; then
        dest_dir="$HOME/Applications"
        mkdir -p "$dest_dir"
    fi
    if ! ditto "$tmp/app/Ollama.app" "$dest_dir/Ollama.app"; then
        warn "não foi possível copiar o Ollama.app para $dest_dir"
        rm -rf "$tmp"
        return 1
    fi
    rm -rf "$tmp"
    OLLAMA_APP="$dest_dir/Ollama.app"
    echo "$OLLAMA_APP" > "$STATE_DIR/ollama-instalado-pelo-nicx"
    info "Ollama instalado em $OLLAMA_APP"
}

install_ollama_macos() {
    if ! find_ollama_app; then
        local method="$OLLAMA_METHOD"
        if [[ "$method" == "auto" ]]; then
            method=download
            [[ -n "$BREW" ]] && method=brew
        fi
        case "$method" in
            brew)
                if [[ -z "$BREW" ]]; then
                    echo "install.sh: NICX_OLLAMA_METHOD=brew, mas o Homebrew não está instalado." >&2
                    return 1
                fi
                info "instalando o Ollama pelo Homebrew..."
                if HOMEBREW_NO_ENV_HINTS=1 "$BREW" install ollama && command -v ollama >/dev/null 2>&1; then
                    return 0
                fi
                warn "o Homebrew não instalou o Ollama; baixando o app oficial."
                download_ollama_app || return 1
                ;;
            download)
                download_ollama_app || return 1
                ;;
            *)
                echo "install.sh: NICX_OLLAMA_METHOD inválido: $OLLAMA_METHOD (use auto, brew ou download)" >&2
                return 1
                ;;
        esac
    fi
    # The app offers to link its CLI into /usr/local/bin, which needs an
    # admin password. A link in ~/.local/bin works without one.
    mkdir -p "$HOME/.local/bin" || return 1
    ln -sf "$OLLAMA_APP/Contents/Resources/ollama" "$HOME/.local/bin/ollama" || return 1
    command -v ollama >/dev/null 2>&1 || return 1
    info "comando 'ollama' ligado em ~/.local/bin (app: $OLLAMA_APP)"
}

OLLAMA_OK=1

install_ollama() {
    if [[ "$SKIP_OLLAMA" -eq 1 ]]; then
        info "pulado (NICX_SKIP_OLLAMA)"
        return 0
    fi
    if command -v ollama >/dev/null 2>&1; then
        info "Ollama já instalado ($(command -v ollama))"
        return 0
    fi
    # Not fatal: everything else still installs, and the final message says
    # how to finish. Rerunning the installer tries again.
    case "$OS_NAME" in
        Darwin) install_ollama_macos || OLLAMA_OK=0 ;;
        *) curl -fsSL https://ollama.com/install.sh | sh || OLLAMA_OK=0 ;;
    esac
    if [[ "$OLLAMA_OK" -ne 1 ]]; then
        warn "o Ollama não foi instalado. Instale pelo site oficial (ollama.com/download) e rode este instalador de novo."
    fi
}

# ok | skipped | failed | none
MODEL_STATE="none"
MODEL=""

pull_default_model() {
    MODEL="$(config_model)"
    if [[ "$MODEL" == "-" ]]; then
        info "a configuração usa outro motor; nada a baixar"
        MODEL_STATE="none"
        return 0
    fi
    if [[ "$SKIP_MODEL" -eq 1 ]]; then
        info "pulado (NICX_SKIP_MODEL / --minimal): baixe depois com 'ollama pull $MODEL'"
        MODEL_STATE="skipped"
        return 0
    fi
    if ! command -v ollama >/dev/null 2>&1; then
        warn "Ollama não encontrado; baixe o modelo depois com 'ollama pull $MODEL'"
        MODEL_STATE="failed"
        return 0
    fi
    local started_pid=""
    if ! ollama_up; then
        mkdir -p "$NICX_HOME/logs"
        nohup ollama serve >"$NICX_HOME/logs/ollama-instalador.log" 2>&1 &
        started_pid=$!
        local waited=0
        while ! ollama_up; do
            if (( waited >= 60 )); then
                warn "o Ollama não respondeu em 60 s; veja $NICX_HOME/logs/ollama-instalador.log"
                break
            fi
            sleep 1
            waited=$((waited + 1))
        done
    fi
    # awk reads the whole listing (no early exit), so pipefail can't turn a
    # match into a SIGPIPE failure.
    if ollama list 2>/dev/null | awk -v m="$MODEL" 'NR > 1 && $1 == m {found = 1} END {exit !found}'; then
        info "modelo $MODEL já baixado"
        MODEL_STATE="ok"
    else
        info "baixando o modelo $MODEL (alguns GB; pode demorar)..."
        if ollama pull "$MODEL"; then
            MODEL_STATE="ok"
        else
            warn "o download do modelo falhou; o Nicx tenta de novo em segundo plano"
            MODEL_STATE="failed"
        fi
    fi
    # Nicx starts Ollama on demand and stops it when it exits; don't leave
    # a server running just because the installer needed one.
    if [[ -n "$started_pid" ]]; then
        kill "$started_pid" 2>/dev/null || true
    fi
}

# ---- launchers ----
install_symlinks() {
    mkdir -p "$HOME/.local/bin"
    ln -sf "$SCRIPTS_DIR/nicx-wrapper.sh" "$HOME/.local/bin/nicx"
    ln -sf "$SCRIPTS_DIR/nicx-uninstall.sh" "$HOME/.local/bin/nicx-uninstall"
    ln -sf "$SCRIPTS_DIR/nicx-abrir.sh" "$HOME/.local/bin/nicx-abrir"
    if [[ "$OS_NAME" == "Darwin" ]]; then
        install_mac_launcher
    fi
}

install_mac_launcher() {
    # A tiny app in ~/Applications (Launchpad/Spotlight: "Nicx") that runs
    # nicx-abrir. Built locally, so Gatekeeper has nothing to quarantine.
    local app="$MAC_LAUNCHER"
    rm -rf "$app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
    cat > "$app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Nicx</string>
    <key>CFBundleDisplayName</key>
    <string>Nicx</string>
    <key>CFBundleIdentifier</key>
    <string>br.com.falkyria.nicx.abrir</string>
    <key>CFBundleExecutable</key>
    <string>Nicx</string>
    <key>CFBundleIconFile</key>
    <string>nicx</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
</dict>
</plist>
EOF
    cat > "$app/Contents/MacOS/Nicx" <<EOF
#!/bin/bash
# Criado pelo instalador do Nicx: liga o servidor e abre a interface.
exec "$SCRIPTS_DIR/nicx-abrir.sh" "\$@"
EOF
    chmod +x "$app/Contents/MacOS/Nicx"
    local png="$SRC_DIR/assets/Nicx_Circular_Logo.png"
    if [[ -f "$png" ]] && command -v sips >/dev/null 2>&1; then
        sips -s format icns "$png" --out "$app/Contents/Resources/nicx.icns" >/dev/null 2>&1 || true
    fi
    touch "$app"
}

PATH_MODIFIED=0
PATH_MODIFIED_RC=""
PATH_MARKER="# Nicx: comandos em ~/.local/bin"

shell_rc_file() {
    local shell_name="${SHELL:-}"
    shell_name="${shell_name##*/}"
    case "$shell_name" in
        zsh) echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
        bash)
            if [[ "$OS_NAME" == "Darwin" ]]; then
                # Terminal.app starts login shells, which read only the first
                # of these. Creating .bash_profile would hide an existing
                # .profile, so reuse whichever is already there.
                if [[ -f "$HOME/.bash_profile" ]]; then echo "$HOME/.bash_profile"
                elif [[ -f "$HOME/.bash_login" ]]; then echo "$HOME/.bash_login"
                elif [[ -f "$HOME/.profile" ]]; then echo "$HOME/.profile"
                else echo "$HOME/.bash_profile"
                fi
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        fish) echo "" ;;
        *) echo "$HOME/.profile" ;;
    esac
}

ensure_path() {
    case ":$ORIG_PATH:" in
        *":$HOME/.local/bin:"*) return 0 ;;
    esac
    local rc
    rc="$(shell_rc_file)"
    if [[ -z "$rc" ]]; then
        info "fish: rode 'fish_add_path ~/.local/bin' para usar os comandos do Nicx"
        return 0
    fi
    PATH_MODIFIED=1
    PATH_MODIFIED_RC="$rc"
    if grep -qxF "$PATH_MARKER" "$rc" 2>/dev/null || grep -qx '# Nicx' "$rc" 2>/dev/null; then
        return 0
    fi
    {
        echo ''
        echo "$PATH_MARKER"
        # shellcheck disable=SC2016 # written literally, expanded by the shell rc
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$rc"
    info "PATH atualizado em $rc"
}

install_launchd() {
    # Opt-in (--servico): start `nicx serve` at login on loopback only.
    local tpl="$SRC_DIR/deploy/launchd/com.nicx.plist"
    local dest_dir="$HOME/Library/LaunchAgents"
    local dest="$dest_dir/$LAUNCHD_LABEL.plist"
    if [[ ! -f "$tpl" ]]; then
        warn "modelo do launchd não encontrado ($tpl)"
        return 0
    fi
    mkdir -p "$dest_dir" "$NICX_HOME/logs"
    local esc_bin esc_logs esc_path
    esc_bin="$(printf '%s' "$HOME/.local/bin/nicx" | sed -e 's/[#&\\]/\\&/g')"
    esc_logs="$(printf '%s' "$NICX_HOME/logs" | sed -e 's/[#&\\]/\\&/g')"
    esc_path="$(printf '%s' "$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" | sed -e 's/[#&\\]/\\&/g')"
    sed -e "s#__NICX_BIN__#$esc_bin#g" \
        -e "s#__NICX_LOGS__#$esc_logs#g" \
        -e "s#__NICX_PATH__#$esc_path#g" \
        "$tpl" > "$dest.tmp"
    mv "$dest.tmp" "$dest"
    local domain
    domain="gui/$(id -u)"
    launchctl bootout "$domain/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
    if launchctl bootstrap "$domain" "$dest" 2>/dev/null; then
        info "serviço ligado: o Nicx inicia sozinho ao entrar no macOS ($dest)"
    else
        warn "não foi possível ligar o serviço agora; ele liga no próximo login ($dest)"
    fi
}

detach_bg_orchestrator() {
    if [[ "$SKIP_BG" -eq 1 ]]; then
        info "--no-bg-orchestrator: nada em segundo plano"
        return 0
    fi
    # Background: Rust toolchain + the nicx_rust extension (needed by the
    # agents with tools) and, only if the foreground pull failed, another
    # try at the model. Never bigger models nobody asked for.
    local models=()
    if [[ "$MODEL_STATE" == "failed" && -n "$MODEL" ]] && command -v ollama >/dev/null 2>&1; then
        models=("$MODEL")
    fi
    nohup "$SCRIPTS_DIR/bg-orchestrator.sh" ${models[@]+"${models[@]}"} \
        > "$STATE_DIR/bg-orchestrator.log" 2>&1 &
    disown
}

# ---- run ----
echo "Instalador do Nicx"
echo "  pasta:       $NICX_HOME"
if [[ "$OS_NAME" == "Darwin" ]]; then
    macos_preflight
else
    echo "  WSL2:        $WSL"
fi
echo

choose_analytics
beacon "install_started"
choose_model

step install_uv         "Instalar o uv"                    install_uv
step clone_repo         "Baixar o código do Nicx"          clone_repo
step copy_scripts       "Copiar os scripts de instalação"  copy_scripts
step create_venv        "Criar o ambiente Python"          create_venv
step editable_install   "Instalar o Nicx e dependências"   editable_install
check build_interface   "Interface web"                    build_interface
check write_config      "Configuração (config.toml)"       write_config
persist_analytics_choice
check install_ollama    "Ollama"                           install_ollama
check pull_default_model "Modelo de IA"                    pull_default_model
check install_symlinks  "Atalhos (nicx, nicx-abrir, nicx-uninstall)" install_symlinks
check ensure_path       "PATH do terminal"                 ensure_path
if [[ "$WANT_LAUNCHD" -eq 1 ]]; then
    if [[ "$OS_NAME" == "Darwin" ]]; then
        check install_launchd "Serviço ao entrar no macOS" install_launchd
    else
        warn "--servico só existe no macOS (no Linux veja deploy/systemd/)"
    fi
fi
step detach_bg_orchestrator "Tarefas em segundo plano" detach_bg_orchestrator

INSTALL_TOTAL_MS=$(( ( $(date +%s) - INSTALL_START_EPOCH ) * 1000 ))
beacon "install_completed" "" "$INSTALL_TOTAL_MS"
# Clear ERR trap — we succeeded; any later non-zero exit shouldn't beacon a failure.
trap - ERR

echo
echo "Pronto! O Nicx está instalado."
echo

if [[ "$PATH_MODIFIED" -eq 1 ]]; then
    cat <<EOF
Abra um Terminal novo para usar os comandos (ou rode: source $PATH_MODIFIED_RC).

EOF
fi

if [[ "$OS_NAME" == "Darwin" ]]; then
    cat <<EOF
Para abrir: procure "Nicx" no Launchpad ou no Spotlight, ou rode: nicx-abrir
  (liga o Nicx e abre http://127.0.0.1:8000 no navegador)
EOF
else
    cat <<EOF
Para abrir: nicx-abrir  (liga o Nicx e abre http://127.0.0.1:8000 no navegador)
EOF
fi
cat <<EOF
No terminal:  nicx chat   |   nicx ask "Quem é você?"   |   nicx doctor
Desinstalar:  nicx-uninstall

EOF

if [[ "$OLLAMA_OK" -ne 1 ]]; then
    cat <<EOF
AVISO: o Ollama não foi instalado (ele roda o modelo de IA). Instale pelo site
oficial, ollama.com/download, e rode este instalador de novo.

EOF
fi

if [[ "$INTERFACE_OK" -ne 1 ]]; then
    cat <<EOF
AVISO: a interface web não foi compilada; o 'nicx chat' funciona. Para tentar
de novo, rode este instalador outra vez.

EOF
fi

case "$MODEL_STATE" in
    skipped)
        echo "O modelo não foi baixado (--minimal). Baixe com: ollama pull $MODEL"
        echo
        ;;
    failed)
        cat <<EOF
AVISO: o modelo $MODEL não terminou de baixar. Ele é tentado de novo em segundo
plano; acompanhe com 'nicx doctor' ou baixe com: ollama pull $MODEL

EOF
        ;;
esac

if [[ "$SKIP_BG" -ne 1 ]]; then
    cat <<EOF
Em segundo plano (pode fechar o Terminal): Rust e a extensão nativa do Nicx,
usada pelos agentes com ferramentas. Veja o andamento com 'nicx doctor'.
EOF
fi

exit 0
}  # end of the whole-script block (see the top)
