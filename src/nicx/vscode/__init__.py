"""Ligar o Nicx ao VS Code: instala a extensão "Nicx para VS Code".

O pacote da extensão (``nicx.vsix``, ~30 KB) vem junto com o Nicx (gerado de
``vscode/`` pelo ``build-installer.ps1``). :func:`servico.instalar` acha o
``code`` do VS Code (ou do VS Code Insiders / VSCodium) e roda
``code --install-extension``.
"""

from __future__ import annotations
