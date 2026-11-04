"""Cifra do backup: scrypt (chave da senha) + AES-256-GCM, tudo no PC.

O envelope guarda o sal, o nonce e os parâmetros; sem a senha do backup não há
como abrir, nem no servidor da Falkyria. Senha esquecida = backup perdido.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import zlib

FORMATO = 1
_N, _R, _P = 2**15, 8, 1
_AAD = b"nicx-backup-1"
MIN_SENHA = 8


class SenhaErrada(ValueError):
    """A senha do backup não abre este backup."""


def _chave(senha: str, sal: bytes, n: int = _N, r: int = _R, p: int = _P) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"),
        salt=sal,
        n=n,
        r=r,
        p=p,
        maxmem=128 * 1024 * 1024,
        dklen=32,
    )


def cifrar(texto: str, senha: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(senha) < MIN_SENHA:
        raise ValueError(
            f"a senha do backup precisa de pelo menos {MIN_SENHA} caracteres"
        )
    sal, nonce = os.urandom(16), os.urandom(12)
    dados = AESGCM(_chave(senha, sal)).encrypt(
        nonce, zlib.compress(texto.encode("utf-8"), 9), _AAD
    )
    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return json.dumps(
        {
            "v": FORMATO,
            "kdf": "scrypt",
            "n": _N,
            "r": _R,
            "p": _P,
            "sal": b64(sal),
            "nonce": b64(nonce),
            "dados": b64(dados),
        }
    )


def decifrar(envelope: str, senha: str) -> str:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        e = json.loads(envelope)
        if e.get("v") != FORMATO or e.get("kdf") != "scrypt":
            raise SenhaErrada("formato de backup desconhecido")
        chave = _chave(
            senha, base64.b64decode(e["sal"]), int(e["n"]), int(e["r"]), int(e["p"])
        )
        claro = AESGCM(chave).decrypt(
            base64.b64decode(e["nonce"]), base64.b64decode(e["dados"]), _AAD
        )
    except InvalidTag as exc:
        raise SenhaErrada("senha do backup errada") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise SenhaErrada("backup ilegível") from exc
    return zlib.decompress(claro).decode("utf-8")


__all__ = ["MIN_SENHA", "SenhaErrada", "cifrar", "decifrar"]
