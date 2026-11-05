"""Imagens anexadas: conferir e reduzir antes de irem para o modelo.

O app já reduz no navegador, mas a API local aceita qualquer cliente: aqui
cada imagem é aberta de verdade (não basta parecer base64), girada conforme
o EXIF e reduzida para no máximo :data:`LADO` px. Imagem grande custa tokens
(e minutos na CPU): 512 px já dão ~220 tokens no ``qwen3.5:4b``.
"""

from __future__ import annotations

import base64
import binascii
import io

from nicx.anexos import AnexoInvalido

MAX_IMAGENS = 4
MAX_BYTES = 8 * 1024 * 1024
LADO = 640


def _decodificar(item: str) -> bytes:
    texto = (item or "").strip()
    if texto.startswith("data:"):
        _, _, texto = texto.partition(",")
    try:
        return base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AnexoInvalido("uma das imagens não veio em base64 válido") from exc


def reduzir(dados: bytes, lado: int = LADO) -> str:
    """A imagem em JPEG (ou PNG, se já pequena) com no máximo *lado* px, em base64."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(dados) > MAX_BYTES:
        raise AnexoInvalido("imagem grande demais (máximo de 8 MB)")
    try:
        with Image.open(io.BytesIO(dados)) as aberta:
            formato = aberta.format
            # 0x0112 = orientação do EXIF (foto de celular "de lado").
            girada = aberta.getexif().get(0x0112, 1) != 1
            img = ImageOps.exif_transpose(aberta)
            pequena = max(img.size) <= lado
            if pequena and not girada and formato in ("JPEG", "PNG"):
                return base64.b64encode(dados).decode("ascii")
            img.thumbnail((lado, lado))
            if img.mode not in ("RGB", "L"):
                fundo = Image.new("RGB", img.size, (255, 255, 255))
                com_alfa = img.convert("RGBA")
                fundo.paste(com_alfa, mask=com_alfa.getchannel("A"))
                img = fundo
            saida = io.BytesIO()
            img.save(saida, "JPEG", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AnexoInvalido("não consegui abrir uma das imagens") from exc
    return base64.b64encode(saida.getvalue()).decode("ascii")


def preparar(lista: list[str], lado: int = LADO) -> list[str]:
    """Confere e reduz as imagens de uma mensagem (base64, sem o prefixo data:)."""
    if len(lista) > MAX_IMAGENS:
        raise AnexoInvalido(f"no máximo {MAX_IMAGENS} imagens por mensagem")
    return [reduzir(_decodificar(item), lado) for item in lista]


__all__ = ["LADO", "MAX_BYTES", "MAX_IMAGENS", "preparar", "reduzir"]
