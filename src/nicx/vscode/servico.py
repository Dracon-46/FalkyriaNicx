"""Achar o VS Code e instalar (ou atualizar) a extensão do Nicx nele."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ID_EXTENSAO = "falkyria.nicx"
_PACOTE = Path(__file__).with_name("nicx.vsix")


class VSCodeErro(RuntimeError):
    """Não deu para ligar ao VS Code; a mensagem diz por quê (em português)."""


def pacote() -> Optional[Path]:
    return _PACOTE if _PACOTE.is_file() else None


def _candidatos() -> list[Path]:
    nomes = ["code", "code-insiders", "codium"]
    achados = [Path(p) for n in nomes if (p := shutil.which(n))]
    if sys.platform == "win32":
        locais = os.environ.get("LOCALAPPDATA", "")
        programas = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramW6432", ""),
        ]
        for base, pasta in [
            (locais, r"Programs\Microsoft VS Code"),
            (locais, r"Programs\Microsoft VS Code Insiders"),
            (locais, r"Programs\VSCodium"),
            *[(p, "Microsoft VS Code") for p in programas],
        ]:
            if base:
                achados += list((Path(base) / pasta / "bin").glob("code*.cmd"))
                achados += list((Path(base) / pasta / "bin").glob("codium*.cmd"))
    elif sys.platform == "darwin":
        achados.append(
            Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
        )
    vistos, unicos = set(), []
    for c in achados:
        chave = str(c).lower()
        if chave not in vistos and c.is_file():
            vistos.add(chave)
            unicos.append(c)
    return unicos


def achar_code() -> Optional[Path]:
    """O comando ``code`` do VS Code instalado (ou ``None``)."""
    lista = _candidatos()
    return lista[0] if lista else None


def _rodar(
    code: Path, *args: str, timeout: float = 120.0
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(code), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def versao_instalada(code: Optional[Path] = None) -> Optional[str]:
    code = code or achar_code()
    if code is None:
        return None
    try:
        r = _rodar(code, "--list-extensions", "--show-versions", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for linha in r.stdout.splitlines():
        nome, _, versao = linha.strip().partition("@")
        if nome.lower() == ID_EXTENSAO:
            return versao or "?"
    return None


def estado() -> dict:
    code = achar_code()
    return {
        "vscode": bool(code),
        "pacote": bool(pacote()),
        "instalada": versao_instalada(code) if code else None,
    }


def instalar() -> dict:
    vsix = pacote()
    if vsix is None:
        raise VSCodeErro("a extensão não veio com esta instalação do Nicx")
    code = achar_code()
    if code is None:
        raise VSCodeErro(
            "não achei o VS Code neste PC. Instale o VS Code e tente de novo"
        )
    try:
        r = _rodar(code, "--install-extension", str(vsix), "--force")
    except subprocess.TimeoutExpired as exc:
        raise VSCodeErro("o VS Code demorou demais para instalar a extensão") from exc
    except OSError as exc:
        raise VSCodeErro(f"não consegui abrir o VS Code ({exc})") from exc
    if r.returncode != 0:
        detalhe = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["erro"]
        raise VSCodeErro(f"o VS Code recusou a extensão: {detalhe[0][:200]}")
    return estado()


__all__ = ["ID_EXTENSAO", "VSCodeErro", "achar_code", "estado", "instalar", "pacote"]
