"""Comparar caminhos de pastas dos projetos em qualquer sistema.

Um caminho do Windows (``C:\\dev\\site``) segue as regras do Windows, que não
diferenciam maiúsculas e aceitam as duas barras, mesmo quando o Nicx roda em
outro sistema (dados copiados, testes); os outros seguem as regras do POSIX.
"""

from __future__ import annotations

import ntpath
import posixpath
import re
import sys
from pathlib import PurePosixPath, PureWindowsPath

_WINDOWS = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def eh_windows(caminho: str) -> bool:
    return sys.platform == "win32" or bool(_WINDOWS.match(caminho))


def chave(caminho: str) -> str:
    """Forma comparável: mesma pasta, mesma chave."""
    caminho = caminho.strip()
    if not caminho:
        return ""
    if eh_windows(caminho):
        return ntpath.normcase(ntpath.normpath(caminho)).rstrip("\\/") or "\\"
    return posixpath.normpath(caminho).rstrip("/") or "/"


def separador(caminho: str) -> str:
    return "\\" if eh_windows(caminho) else "/"


def nome(caminho: str) -> str:
    """Nome da última pasta (``C:\\dev\\site`` -> ``site``)."""
    if eh_windows(caminho):
        return PureWindowsPath(caminho).name
    return PurePosixPath(caminho).name


def mesmo_nome(a: str, b: str) -> bool:
    if eh_windows(a) or eh_windows(b):
        return a.strip().casefold() == b.strip().casefold()
    return a.strip() == b.strip()


__all__ = ["chave", "eh_windows", "mesmo_nome", "nome", "separador"]
