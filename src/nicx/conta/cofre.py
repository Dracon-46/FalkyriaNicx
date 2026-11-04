"""A sessão da Conta Falkyria no PC: ``~/.nicx/conta.bin``.

No Windows o conteúdo é cifrado com a DPAPI (só o seu usuário do Windows, neste
PC, consegue abrir). Em outros sistemas fica em texto com permissão só para o
dono do arquivo. A senha nunca é guardada: só os tokens da sessão.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
_ENTROPIA = b"nicx-conta-falkyria"


def caminho() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "conta.bin"


def protegido() -> bool:
    return sys.platform == "win32"


def _dpapi(dados: bytes, cifrar: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    def blob(b: bytes) -> Blob:
        buffer = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    entrada, entropia, saida = blob(dados), blob(_ENTROPIA), Blob()
    funcao = crypt32.CryptProtectData if cifrar else crypt32.CryptUnprotectData
    ok = funcao(
        ctypes.byref(entrada), None, ctypes.byref(entropia), None, None, 0x1,
        ctypes.byref(saida),
    )  # fmt: skip
    if not ok:
        raise OSError("DPAPI recusou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(saida.pbData)


def gravar(sessao: dict[str, Any]) -> None:
    dados = json.dumps(sessao).encode("utf-8")
    if protegido():
        dados = _dpapi(dados, cifrar=True)
    arquivo = caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_bytes(dados)
    if not protegido():
        os.chmod(tmp, 0o600)
    os.replace(tmp, arquivo)


def ler() -> Optional[dict[str, Any]]:
    arquivo = caminho()
    if not arquivo.exists():
        return None
    try:
        dados = arquivo.read_bytes()
        if protegido():
            dados = _dpapi(dados, cifrar=False)
        sessao = json.loads(dados.decode("utf-8"))
    except (OSError, ValueError):
        logger.warning("Sessão da conta ilegível: saindo da conta")
        apagar()
        return None
    return sessao if isinstance(sessao, dict) else None


def apagar() -> None:
    caminho().unlink(missing_ok=True)


__all__ = ["apagar", "caminho", "gravar", "ler", "protegido"]
