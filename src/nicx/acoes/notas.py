"""Anotações rápidas: "anota: comprar pão". Ficam em ~/.nicx/notas.md.

Um arquivo Markdown comum, uma nota por linha ("- [27/10 14:05] comprar pão"),
para a pessoa poder abrir, editar ou apagar à mão.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List

_LINE = re.compile(r"^- \[[^\]]*\] (?P<text>.+)$")


def path() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "notas.md"


def add(text: str) -> None:
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%d/%m %H:%M")
    with file.open("a", encoding="utf-8") as fh:
        if fh.tell() == 0:
            fh.write("# Anotações do Nicx\n\n")
        fh.write(f"- [{stamp}] {text.strip()}\n")


def all_notes() -> List[str]:
    file = path()
    if not file.exists():
        return []
    notes = []
    for line in file.read_text(encoding="utf-8").splitlines():
        m = _LINE.match(line.strip())
        if m:
            notes.append(m.group("text"))
    return notes


def clear() -> int:
    """Apaga as anotações do Nicx. Texto escrito à mão no arquivo fica, e uma
    cópia do arquivo antes de apagar vai para notas.md.bak."""
    count = len(all_notes())
    file = path()
    if file.exists() and count:
        text = file.read_text(encoding="utf-8")
        file.with_suffix(".md.bak").write_text(text, encoding="utf-8")
        kept = [line for line in text.splitlines() if not line.startswith("- [")]
        file.write_text("\n".join(kept).rstrip() + "\n\n", encoding="utf-8")
    return count
