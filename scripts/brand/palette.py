"""Apply the Falkyria palette (from falkyria-lumen) to frontend/src/index.css."""

import re
import sys
from pathlib import Path

LIGHT = {
    "--color-bg": "#f6f6f4",
    "--color-bg-secondary": "#f0efec",
    "--color-bg-tertiary": "#e6e4df",
    "--color-surface": "#fcfcfb",
    "--color-sidebar": "rgba(252, 252, 251, 0.85)",
    "--color-border": "rgba(11, 11, 11, 0.09)",
    "--color-border-subtle": "rgba(11, 11, 11, 0.05)",
    "--color-text": "#0b0b0b",
    "--color-text-secondary": "#6b6964",
    "--color-text-tertiary": "#a3a19a",
    "--color-text-inverse": "#fcfcfb",
    "--color-accent": "#1c5cab",
    "--color-accent-hover": "#164a8a",
    "--color-accent-subtle": "rgba(28, 92, 171, 0.08)",
    "--color-accent-glow": "rgba(28, 92, 171, 0.25)",
    "--color-accent-amber": "#eda100",
    "--color-accent-amber-hover": "#c98500",
    "--color-accent-amber-subtle": "rgba(237, 161, 0, 0.12)",
    "--color-accent-blue-subtle": "rgba(28, 92, 171, 0.08)",
    "--color-success": "#0a7a33",
    "--color-warning": "#9a6500",
    "--color-error": "#b42318",
    "--color-code-bg": "#f0efec",
    "--color-input-bg": "#fcfcfb",
    "--color-input-border": "#c7c4bc",
    "--color-user-bubble": "#0b0b0b",
    "--color-user-bubble-text": "#fcfcfb",
    "--color-on-accent": "#ffffff",
    "--color-disabled-bg": "#e6e4df",
    "--font-display": "'Geist Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
}

DARK = {
    "--color-bg": "#121211",
    "--color-bg-secondary": "#1a1a19",
    "--color-bg-tertiary": "#24241f",
    "--color-surface": "#1a1a19",
    "--color-sidebar": "rgba(18, 18, 17, 0.72)",
    "--color-border": "rgba(255, 255, 255, 0.09)",
    "--color-border-subtle": "rgba(255, 255, 255, 0.05)",
    "--color-text": "#f4f4f1",
    "--color-text-secondary": "#a3a297",
    "--color-text-tertiary": "#6b6a63",
    "--color-text-inverse": "#121211",
    "--color-accent": "#86b6ef",
    "--color-accent-hover": "#a9cbf4",
    "--color-accent-subtle": "rgba(134, 182, 239, 0.12)",
    "--color-accent-glow": "rgba(134, 182, 239, 0.3)",
    "--color-accent-amber": "#eda100",
    "--color-accent-amber-hover": "#f5b733",
    "--color-accent-amber-subtle": "rgba(237, 161, 0, 0.14)",
    "--color-accent-blue-subtle": "rgba(134, 182, 239, 0.12)",
    "--color-success": "#5fd08a",
    "--color-warning": "#e6b04a",
    "--color-error": "#ff8a7a",
    "--color-code-bg": "#1a1a19",
    "--color-input-bg": "#1a1a19",
    "--color-input-border": "rgba(255, 255, 255, 0.12)",
    "--color-user-bubble": "#24241f",
    "--color-user-bubble-text": "#f4f4f1",
    "--color-on-accent": "#0b0b0b",
    "--color-disabled-bg": "#24241f",
    "--shadow-md": "0 4px 14px -2px rgb(0 0 0 / 0.5), 0 0 0 1px rgba(255, 255, 255, 0.04)",
    "--shadow-lg": "0 18px 40px -12px rgb(0 0 0 / 0.7), 0 0 0 1px rgba(255, 255, 255, 0.06)",
}


def patch_block(css: str, opener: str, values: dict) -> str:
    start = css.index(opener)
    end = css.index("}", start)
    block = css[start:end]
    for var, val in values.items():
        block, n = re.subn(
            rf"({re.escape(var)}:\s*)[^;]+;", lambda m: f"{m.group(1)}{val};", block
        )
        if n == 0 and var.startswith("--font"):
            continue
        if n != 1:
            raise SystemExit(f"{opener!r}: {var} matched {n} times")
    return css[:start] + block + css[end:]


path = Path(sys.argv[1])
css = path.read_text(encoding="utf-8")
css = patch_block(css, "  :root {\n    --color-bg:", LIGHT)
css = patch_block(css, "  .dark {\n    --color-bg:", DARK)
css = patch_block(css, "    :root:not(.light) {\n      --color-bg:", DARK)
css = css.replace(
    " * Nicx design tokens.\n * Zinc/slate neutrals, blue accent.",
    " * Nicx design tokens — Falkyria palette (shared with Lumen).\n"
    " * Warm neutrals, blue accent, amber signature.",
)
path.write_text(css, encoding="utf-8", newline="")
print("ok")
