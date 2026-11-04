"""Assinatura dos pacotes da loja (Ed25519).

A Falkyria assina cada pacote no próprio PC (``nicx loja assinar``) com a chave
privada em ``~/.falkyria-loja/`` (fora do repositório e do ``NICX_HOME``). O
app só aceita da loja o pacote cujo texto bate com a impressão digital
(sha256) e com a assinatura de uma chave de :data:`CHAVES_CONFIAVEIS`.

O texto assinado é o JSON canônico do pacote (:func:`canonico`): chaves em
ordem, sem espaços. É esse texto, e não um JSON reformatado, que vai para o
banco e volta para o app.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from nicx.extensoes.loja_chaves import CHAVES_CONFIAVEIS

FORMATO_ASSINADO = 1


class AssinaturaInvalida(ValueError):
    """O pacote não é o que a Falkyria assinou."""


def canonico(pacote: dict[str, Any]) -> str:
    return json.dumps(pacote, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def impressao(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def id_da_chave(publica: bytes) -> str:
    return hashlib.sha256(publica).hexdigest()[:16]


def pasta_da_chave() -> Path:
    return Path.home() / ".falkyria-loja"


def _arquivo_privado(pasta: Path) -> Path:
    return pasta / "chave-privada.pem"


def gerar_chave(pasta: Path | None = None) -> tuple[str, str]:
    """Cria o par de chaves. Devolve ``(id, chave pública em base64)``.

    Não sobrescreve: perder a chave antiga sem querer invalidaria tudo que ela
    assinou.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pasta = pasta or pasta_da_chave()
    arquivo = _arquivo_privado(pasta)
    if arquivo.exists():
        raise FileExistsError(str(arquivo))
    pasta.mkdir(parents=True, exist_ok=True)
    privada = Ed25519PrivateKey.generate()
    arquivo.write_bytes(
        privada.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    publica = privada.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    b64 = base64.b64encode(publica).decode("ascii")
    (pasta / "chave-publica.txt").write_text(
        f"{id_da_chave(publica)} {b64}\n", encoding="utf-8"
    )
    return id_da_chave(publica), b64


def assinar(pacote: dict[str, Any], pasta: Path | None = None) -> dict[str, Any]:
    """O arquivo assinado que vai para o Painel Falkyria."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    arquivo = _arquivo_privado(pasta or pasta_da_chave())
    privada = serialization.load_pem_private_key(arquivo.read_bytes(), password=None)
    if not isinstance(privada, Ed25519PrivateKey):
        raise AssinaturaInvalida("a chave guardada não é Ed25519")
    publica = privada.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    texto = canonico(pacote)
    return {
        "formato_assinado": FORMATO_ASSINADO,
        "id": pacote.get("id", ""),
        "versao": pacote.get("versao", ""),
        "conteudo": texto,
        "sha256": impressao(texto),
        "assinatura": base64.b64encode(privada.sign(texto.encode("utf-8"))).decode(),
        "chave": id_da_chave(publica),
    }


def verificar(
    conteudo: str,
    sha256: str,
    assinatura: str,
    chave: str,
    confiaveis: dict[str, str] | None = None,
) -> None:
    """Levanta ``AssinaturaInvalida`` se o texto não for o assinado pela Falkyria."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    confiaveis = CHAVES_CONFIAVEIS if confiaveis is None else confiaveis
    if impressao(conteudo) != sha256:
        raise AssinaturaInvalida("o pacote chegou diferente do publicado")
    publica_b64 = confiaveis.get(chave)
    if not publica_b64:
        raise AssinaturaInvalida("assinado por uma chave que o Nicx não conhece")
    try:
        publica = Ed25519PublicKey.from_public_bytes(base64.b64decode(publica_b64))
        publica.verify(base64.b64decode(assinatura), conteudo.encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        raise AssinaturaInvalida("a assinatura não confere") from exc


__all__ = [
    "AssinaturaInvalida",
    "assinar",
    "canonico",
    "gerar_chave",
    "id_da_chave",
    "impressao",
    "pasta_da_chave",
    "verificar",
]
