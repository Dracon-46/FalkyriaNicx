#!/usr/bin/env bash
# nicx-uninstall.sh — remove o Nicx do seu usuário.
#
# Remove:
#   ~/.nicx/                       (código, ambiente Python, configuração e dados)
#   ~/.local/bin/nicx, nicx-abrir, nicx-uninstall
#   ~/Applications/Nicx.app        (macOS)
#   ~/Library/LaunchAgents/br.com.falkyria.nicx.plist (macOS, se ligado)
#   a linha do PATH que o instalador pôs no .zshrc/.bash_profile/.bashrc
#
# Não remove: Ollama e os modelos baixados (~/.ollama), uv, Rust.

set -euo pipefail

NICX_HOME="${NICX_HOME:-$HOME/.nicx}"
ASSUME_YES=false
LAUNCHD_LABEL="br.com.falkyria.nicx"
PATH_MARKER="# Nicx: comandos em ~/.local/bin"

usage() {
    cat <<'EOF'
Usage: nicx-uninstall [-y|--yes]

Remove o Nicx e os dados locais dele. Sem --yes, pede confirmação antes de
apagar configuração, memória, habilidades, bancos de dados e credenciais de
conectores.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes|--sim)
            ASSUME_YES=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Opção desconhecida: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

refuse_unsafe_root() {
    echo "Refusing unsafe NICX_HOME: $NICX_HOME (pasta não parece ser do Nicx; nada foi apagado)" >&2
    exit 2
}

OLLAMA_APP_BY_NICX=""

if [[ -d "$NICX_HOME" ]]; then
    resolved_install_root="$(cd "$NICX_HOME" && pwd -P)"
    resolved_user_home="$(cd "$HOME" && pwd -P)"
    if [[ -z "$resolved_install_root" ]] \
        || [[ "$resolved_install_root" == "/" ]] \
        || [[ "$resolved_install_root" == "$resolved_user_home" ]] \
        || [[ "$resolved_user_home" == "$resolved_install_root"/* ]]; then
        refuse_unsafe_root
    fi

    # Never recursively remove a broad system/temp root, even if an unrelated
    # file happens to resemble an Nicx marker there.
    case "$resolved_install_root" in
        /Users|/home|/opt|/tmp|/private|/private/tmp|/var|/var/tmp|/private/var|/private/var/tmp|/usr|/etc)
            refuse_unsafe_root
            ;;
    esac

    # A path being different from $HOME is not evidence that Nicx owns
    # it.  Require the installer's real, non-symlinked state file and at least
    # one known completed install stage before authorizing recursive removal.
    ownership_marker="$resolved_install_root/.state/install-state.json"
    if [[ ! -f "$ownership_marker" ]] \
        || [[ -L "$ownership_marker" ]] \
        || ! grep -Eq '"(install_uv|clone_repo|copy_scripts|create_venv|editable_install)"[[:space:]]*:[[:space:]]*true' "$ownership_marker"; then
        refuse_unsafe_root
    fi

    # Use the exact physical path that passed every check below as well.
    NICX_HOME="$resolved_install_root"

    if [[ "$ASSUME_YES" != true ]]; then
        cat <<EOF
ATENÇÃO: isto apaga de vez todos os dados do Nicx em:
  $NICX_HOME

Inclui config.toml, SOUL.md/MEMORY.md/USER.md, habilidades, agendamentos,
bancos de telemetria, memória guardada e credenciais de conectores.
EOF
        printf 'Digite "sim" para continuar: '
        reply=""
        read -r reply || true
        case "$reply" in
            sim|SIM|Sim|yes|YES|Yes) ;;
            *)
                echo "O Nicx não foi removido."
                exit 0
                ;;
        esac
    fi

    if [[ -f "$NICX_HOME/.state/ollama-instalado-pelo-nicx" ]]; then
        OLLAMA_APP_BY_NICX="$(cat "$NICX_HOME/.state/ollama-instalado-pelo-nicx" 2>/dev/null || true)"
    fi
fi

# macOS login service (install.sh --servico).
launch_agent="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
if [[ -f "$launch_agent" ]]; then
    launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 \
        || launchctl unload "$launch_agent" >/dev/null 2>&1 || true
    rm -f "$launch_agent"
    echo "Serviço removido: $launch_agent"
fi

# Stop the server (and the Ollama it started) before deleting its files.
if [[ -x "$NICX_HOME/.venv/bin/nicx" ]]; then
    "$NICX_HOME/.venv/bin/nicx" stop >/dev/null 2>&1 || true
fi

if [[ -f "$NICX_HOME/.state/bg.pid" ]]; then
    pid=$(cat "$NICX_HOME/.state/bg.pid" 2>/dev/null || echo "")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Parando as tarefas em segundo plano (pid=$pid)..."
        pkill -TERM -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
    fi
fi

if [[ -d "$NICX_HOME" ]]; then
    rm -rf -- "$NICX_HOME"
    echo "Removido: $NICX_HOME"
fi

for f in "$HOME/.local/bin/nicx" "$HOME/.local/bin/nicx-uninstall" "$HOME/.local/bin/nicx-abrir"; do
    if [[ -L "$f" ]] || [[ -f "$f" ]]; then
        rm -f "$f"
        echo "Removido: $f"
    fi
done

# The ~/Applications launcher, only if it is the one install.sh made.
mac_app="$HOME/Applications/Nicx.app"
if [[ -f "$mac_app/Contents/Info.plist" ]] \
    && grep -q "br.com.falkyria.nicx.abrir" "$mac_app/Contents/Info.plist" 2>/dev/null; then
    rm -rf -- "$mac_app"
    echo "Removido: $mac_app"
fi

# The PATH line install.sh appended: the marker comment plus the export
# right after it. Anything else in the file stays byte for byte.
remove_path_block() {
    local rc="$1" tmp
    [[ -f "$rc" ]] || return 0
    grep -qxF "$PATH_MARKER" "$rc" 2>/dev/null || grep -qx '# Nicx' "$rc" 2>/dev/null || return 0
    tmp="$(mktemp "${TMPDIR:-/tmp}/nicx-rc.XXXXXX")"
    awk -v m1="$PATH_MARKER" -v m2="# Nicx" -v ex='export PATH="$HOME/.local/bin:$PATH"' '
        pending != "" {
            if ($0 == ex) { pending = ""; next }
            print pending
            pending = ""
        }
        $0 == m1 || $0 == m2 { pending = $0; next }
        { print }
        END { if (pending != "") print pending }
    ' "$rc" > "$tmp"
    if ! cmp -s "$rc" "$tmp"; then
        # cat (not mv) keeps the file's permissions and any symlink.
        cat "$tmp" > "$rc"
        echo "PATH do Nicx removido de $rc"
    fi
    rm -f "$tmp"
}
for rc in "${ZDOTDIR:-$HOME}/.zshrc" "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" \
    "$HOME/.bash_login" "$HOME/.profile"; do
    remove_path_block "$rc"
done

ollama_hint="brew uninstall ollama  (ou apague o Ollama.app em Aplicativos)"
if [[ -n "$OLLAMA_APP_BY_NICX" ]]; then
    ollama_hint="rm -rf \"$OLLAMA_APP_BY_NICX\" ~/.local/bin/ollama"
fi

cat <<EOF

Nicx removido.

Mantidos (outros programas podem usar):
  - Ollama e modelos  (remover: $ollama_hint; modelos: rm -rf ~/.ollama)
  - uv                (remover: rm -f ~/.local/bin/uv ~/.local/bin/uvx; rm -rf ~/.local/share/uv)
  - Rust              (remover: rustup self uninstall)
EOF
