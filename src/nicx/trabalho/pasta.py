"""A pasta de trabalho e a guarda dos caminhos.

O modelo só enxerga caminhos relativos à pasta escolhida. Cada caminho é
resolvido (com links simbólicos) e precisa continuar dentro dela; arquivos de
segredo (``.env``, chaves, ``.ssh``...) são recusados como nas outras
ferramentas de arquivo do Nicx.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


class ForaDaPasta(ValueError):
    """Caminho que não pode ser usado; a mensagem diz por quê (em português)."""


def _pastas_proibidas() -> list[Path]:
    """Pastas que nunca viram pasta de trabalho (nem as que as contêm)."""
    lista: list[Path] = []
    for nome in (
        "SystemRoot",
        "windir",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramW6432",
        "ProgramData",
    ):
        valor = os.environ.get(nome)
        if valor:
            lista.append(Path(valor))
    try:
        from nicx.nucleo.paths import get_config_dir

        lista.append(get_config_dir())
    except Exception:  # noqa: BLE001
        pass
    lista.append(Path(sys.prefix).parent)  # a instalação do próprio Nicx
    if sys.platform != "win32":
        lista += [
            Path(p)
            for p in ("/etc", "/usr", "/bin", "/sbin", "/System", "/Library", "/var")
        ]
    return [p.resolve() for p in lista if str(p)]


def validar_pasta(caminho: str) -> Path:
    """A pasta escolhida, resolvida, ou :class:`ForaDaPasta` com o motivo."""
    texto = (caminho or "").strip().strip('"')
    if not texto:
        raise ForaDaPasta("escolha uma pasta")
    pasta = Path(texto).expanduser()
    if not pasta.is_absolute():
        raise ForaDaPasta("use o caminho completo da pasta")
    try:
        pasta = pasta.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ForaDaPasta("a pasta não existe") from exc
    if not pasta.is_dir():
        raise ForaDaPasta("isso não é uma pasta")
    if pasta == Path(pasta.anchor):
        raise ForaDaPasta("escolha uma pasta, não o disco inteiro")
    if pasta == Path.home().resolve():
        raise ForaDaPasta(
            "a pasta do usuário inteira é ampla demais: escolha uma pasta dentro dela"
        )
    for proibida in _pastas_proibidas():
        if (
            pasta == proibida
            or pasta.is_relative_to(proibida)
            or proibida.is_relative_to(pasta)
        ):
            raise ForaDaPasta("essa pasta é do sistema ou do próprio Nicx")
    from nicx.seguranca.file_policy import is_sensitive_file

    if is_sensitive_file(pasta):
        raise ForaDaPasta("essa pasta guarda chaves ou senhas")
    return pasta


class Pasta:
    """Resolve os caminhos que o modelo pede, sempre dentro da pasta."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = Path(raiz).resolve()

    def caminho(self, relativo: str) -> Path:
        texto = (relativo or ".").strip().strip('"').replace("\\", "/")
        if texto in ("", "/"):
            texto = "."
        alvo = Path(texto)
        if alvo.is_absolute():
            p = alvo.resolve()
        else:
            p = (self.raiz / alvo).resolve()
        if p != self.raiz and not p.is_relative_to(self.raiz):
            raise ForaDaPasta(f"'{relativo}' fica fora da pasta de trabalho")
        from nicx.seguranca.file_policy import is_sensitive_file

        if p != self.raiz and is_sensitive_file(p):
            raise ForaDaPasta(
                f"'{relativo}' guarda chaves ou senhas e não pode ser usado"
            )
        return p

    def relativo(self, p: Path) -> str:
        try:
            r = Path(p).resolve().relative_to(self.raiz)
        except ValueError:
            return str(p)
        return "." if str(r) == "." else r.as_posix()


__all__ = ["ForaDaPasta", "Pasta", "validar_pasta"]
