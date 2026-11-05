"""Anexos do chat: imagens e vídeos que a pessoa manda junto com a pergunta.

- :mod:`imagens`: confere e reduz as imagens (até 4 por mensagem, lado de
  640 px) antes de irem para o modelo local, que enxerga (o ``qwen3.5:4b``
  tem visão embutida).
- :mod:`video`: um vídeo vira alguns quadros (imagens) e a transcrição do
  áudio pelo Whisper local. Nada sai do PC e nada fica guardado: o arquivo
  temporário é apagado ao fim.
"""

from __future__ import annotations


class AnexoInvalido(ValueError):
    """Anexo que não dá para usar; a mensagem diz por quê (em português)."""


__all__ = ["AnexoInvalido"]
