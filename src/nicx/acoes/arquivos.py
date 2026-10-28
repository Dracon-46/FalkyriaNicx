"""Arquivos do usuário: achar, listar, abrir e organizar.

O Nicx consulta o PC como a própria pessoa faria: procura nas pastas do
usuário (Área de Trabalho, Documentos, Downloads, Imagens, Vídeos, Músicas,
inclusive no OneDrive), abre com o programa padrão e organiza uma pasta em
subpastas por tipo. Organizar nunca apaga nada, pede confirmação e guarda um
registro para desfazer.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

# Tipo -> (pasta ao organizar, extensões)
CATEGORIES: dict[str, tuple[str, frozenset[str]]] = {
    "imagem": (
        "Imagens",
        frozenset(
            ".jpg .jpeg .png .gif .webp .bmp .heic .heif .tif .tiff .svg .raw".split()
        ),
    ),
    "video": ("Vídeos", frozenset(".mp4 .mkv .mov .avi .wmv .webm .m4v .3gp".split())),
    "musica": (
        "Músicas",
        frozenset(".mp3 .wav .flac .aac .ogg .m4a .wma .opus".split()),
    ),
    "pdf": ("PDFs", frozenset({".pdf"})),
    "documento": (
        "Documentos",
        frozenset(".doc .docx .odt .rtf .txt .md .pages .epub".split()),
    ),
    "planilha": ("Planilhas", frozenset(".xls .xlsx .ods .csv .numbers".split())),
    "apresentacao": ("Apresentações", frozenset(".ppt .pptx .odp .key".split())),
    "compactado": ("Compactados", frozenset(".zip .rar .7z .tar .gz .bz2 .xz".split())),
    "instalador": (
        "Instaladores",
        frozenset(".exe .msi .msix .appx .dmg .deb .rpm .apk".split()),
    ),
    "codigo": (
        "Código",
        frozenset(
            (
                ".py .js .ts .tsx .html .css .json .java .c .cpp .cs .go .rs"
                " .sql .sh .ps1"
            ).split()
        ),
    ),
}
OTHER_FOLDER = "Outros"

# Ainda baixando ou temporário: não mexe.
_PARTIAL = frozenset(".crdownload .part .partial .download .tmp .opdownload".split())
# Pastas que não valem a busca (sistema, dependências, lixeira).
_SKIP_DIRS = frozenset(
    {
        "appdata",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "$recycle.bin",
        ".cache",
        ".nicx",
        "site-packages",
    }
)
# Pastas do usuário onde procurar (relativas ao perfil).
SEARCH_FOLDERS = (
    "Desktop",
    "Documents",
    "Downloads",
    "Pictures",
    "Videos",
    "Music",
    "OneDrive",
)

MAX_SCAN = 60_000
SCAN_SECONDS = 6.0


def kind_of(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    for kind, (_folder, exts) in CATEGORIES.items():
        if ext in exts:
            return kind
    return None


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in text)


def roots(home: Optional[Path] = None) -> List[Path]:
    home = home or Path.home()
    found: List[Path] = []
    for name in SEARCH_FOLDERS:
        path = home / name
        if path.is_dir() and not any(path.is_relative_to(r) for r in found):
            found.append(path)
    return found


def walk(start: Iterable[Path], max_depth: int = 8) -> Iterator[Path]:
    """Arquivos das pastas dadas, sem entrar em pastas de sistema, com limites."""
    deadline = time.monotonic() + SCAN_SECONDS
    seen = 0
    stack = [(Path(p), 0) for p in start]
    while stack:
        folder, depth = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            seen += 1
            if seen > MAX_SCAN or time.monotonic() > deadline:
                return
            name = entry.name
            if name.startswith((".", "~$")):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if depth < max_depth and name.lower() not in _SKIP_DIRS:
                        stack.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError:
                continue


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def search(
    query: str,
    kind: Optional[str] = None,
    where: Optional[List[Path]] = None,
    limit: int = 10,
) -> List[Path]:
    """Arquivos cujo nome tem todas as palavras da busca; os mais novos primeiro."""
    words = _norm(query).split()
    kinds = _kinds(kind)
    found = []
    for path in walk(where or roots()):
        if kinds and kind_of(path) not in kinds:
            continue
        name = _norm(path.stem)
        if all(w in name for w in words):
            found.append(path)
    found.sort(key=_mtime, reverse=True)
    return found[:limit]


def _kinds(kind: Optional[str]) -> set[str]:
    if not kind:
        return set()
    if kind == "documento":  # "abre o documento X" vale para PDF, planilha...
        return {"documento", "pdf", "planilha", "apresentacao"}
    return {kind}


def latest(kind: str, where: Optional[List[Path]] = None) -> Optional[Path]:
    """O arquivo mais novo daquele tipo (a última foto, o último PDF...)."""
    best, best_time = None, 0.0
    kinds = _kinds(kind)
    for path in walk(where or roots()):
        if kind_of(path) in kinds:
            t = _mtime(path)
            if t > best_time:
                best, best_time = path, t
    return best


def screenshots_folders(home: Optional[Path] = None) -> List[Path]:
    """Onde ficam os prints: Imagens\\Screenshots, Imagens\\Nicx e afins."""
    home = home or Path.home()
    candidates = []
    for pics in ("Pictures", "OneDrive/Imagens", "OneDrive/Pictures"):
        for sub in ("Screenshots", "Capturas de Tela", "Capturas de tela", "Nicx"):
            path = home / pics / sub
            if path.is_dir():
                candidates.append(path)
    return candidates


def describe(path: Path, home: Optional[Path] = None) -> str:
    """'relatório.pdf (Downloads)', sem o caminho inteiro."""
    home = home or Path.home()
    try:
        folder = path.parent.relative_to(home)
        where = str(folder).replace("\\", "/")
    except ValueError:
        where = str(path.parent)
    return f"{path.name} ({where})"


def list_folder(folder: Path, limit: int = 15) -> tuple[List[str], int]:
    """Nomes dos itens mais recentes da pasta e o total."""
    try:
        entries = [e for e in folder.iterdir() if not e.name.startswith((".", "~$"))]
    except OSError:
        return [], 0
    entries.sort(key=_mtime, reverse=True)
    names = [f"{e.name}/" if e.is_dir() else e.name for e in entries[:limit]]
    return names, len(entries)


# ---------------------------------------------------------------------------
# Organizar e desfazer
# ---------------------------------------------------------------------------


@dataclass
class Move:
    source: str
    target: str


def plan(folder: Path, now: Optional[float] = None) -> dict[str, List[Path]]:
    """Que arquivos iriam para qual subpasta. Só o primeiro nível da pasta."""
    now = now or time.time()
    groups: dict[str, List[Path]] = {}
    for entry in sorted(folder.iterdir()):
        if not entry.is_file() or entry.name.startswith((".", "~$")):
            continue
        if entry.suffix.lower() in _PARTIAL or entry.name.lower() == "desktop.ini":
            continue
        if now - _mtime(entry) < 120:  # mexido agora (talvez baixando)
            continue
        kind = kind_of(entry)
        target = CATEGORIES[kind][0] if kind else OTHER_FOLDER
        groups.setdefault(target, []).append(entry)
    return groups


def _free_name(target: Path) -> Path:
    if not target.exists():
        return target
    for i in range(2, 1000):
        candidate = target.with_name(f"{target.stem} ({i}){target.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"sem nome livre para {target.name}")


def _log_dir() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "organizacao"


def organize(folder: Path, groups: dict[str, List[Path]]) -> tuple[int, Path]:
    """Move os arquivos e grava o registro para desfazer.

    Devolve (quantos moveu, arquivo do registro).
    """
    moves: List[Move] = []
    for target_name, files in groups.items():
        target_dir = folder / target_name
        target_dir.mkdir(exist_ok=True)
        for source in files:
            if not source.exists():
                continue
            try:
                target = _free_name(target_dir / source.name)
                shutil.move(str(source), str(target))
            except OSError:
                continue  # em uso ou sem permissão: fica onde está
            moves.append(Move(str(source), str(target)))
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    log.write_text(
        json.dumps(
            {"folder": str(folder), "moves": [m.__dict__ for m in moves]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(moves), log


def undo_last() -> Optional[tuple[int, str]]:
    """Desfaz a última organização. Devolve (voltaram, pasta) ou None."""
    log_dir = _log_dir()
    logs = sorted(log_dir.glob("*.json")) if log_dir.is_dir() else []
    if not logs:
        return None
    log = logs[-1]
    data = json.loads(log.read_text(encoding="utf-8"))
    restored = 0
    for move in reversed(data.get("moves", [])):
        source, target = Path(move["source"]), Path(move["target"])
        if not target.exists():
            continue
        try:
            shutil.move(str(target), str(_free_name(source)))
            restored += 1
        except OSError:
            continue
    folder = Path(data.get("folder", ""))
    for target_name in {CATEGORIES[k][0] for k in CATEGORIES} | {OTHER_FOLDER}:
        sub = folder / target_name
        try:
            sub.rmdir()  # só some se ficou vazia
        except OSError:
            pass
    log.rename(log.with_suffix(".desfeito"))
    return restored, folder.name


__all__ = [
    "CATEGORIES",
    "describe",
    "kind_of",
    "latest",
    "list_folder",
    "organize",
    "plan",
    "roots",
    "screenshots_folders",
    "search",
    "undo_last",
    "walk",
]
