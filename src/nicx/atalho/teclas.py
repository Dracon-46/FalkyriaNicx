"""Combinações de teclas do atalho global: leitura, validação e nomes.

Formato gravado no ``config.toml``: modificadores e uma tecla, em minúsculas,
separados por ``+`` (``"ctrl+alt+n"``). A ordem dos modificadores é sempre
ctrl, alt, shift, win. Nada aqui depende do sistema: o registro de verdade
fica em :mod:`nicx.atalho.windows`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Modificadores na ordem canônica, com os bits do ``RegisterHotKey``.
MODIFICADORES: dict[str, int] = {
    "ctrl": 0x0002,
    "alt": 0x0001,
    "shift": 0x0004,
    "win": 0x0008,
}

_SINONIMOS: dict[str, str] = {
    "control": "ctrl",
    "ctl": "ctrl",
    "option": "alt",
    "altgr": "alt",
    "super": "win",
    "meta": "win",
    "cmd": "win",
    "windows": "win",
    "esc": "escape",
    "return": "enter",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "espaco": "space",
    "espaço": "space",
    "cima": "up",
    "baixo": "down",
    "esquerda": "left",
    "direita": "right",
}

# Teclas aceitas (fora letras, números e F1-F24) -> código virtual do Windows.
_TECLAS_ESPECIAIS: dict[str, int] = {
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "backspace": 0x08,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "pause": 0x13,
}

_NOMES_ESPECIAIS: dict[str, str] = {
    "space": "Espaço",
    "enter": "Enter",
    "tab": "Tab",
    "escape": "Esc",
    "backspace": "Backspace",
    "insert": "Insert",
    "delete": "Delete",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
    "pause": "Pause",
}

_NOMES_MODIFICADORES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}

# Combinações do Windows ou de uso geral: registrar uma delas quebraria o
# sistema ou um atalho que todo programa usa.
RESERVADAS: frozenset[str] = frozenset(
    {
        "ctrl+alt+delete",
        "ctrl+shift+escape",
        "ctrl+escape",
        "alt+tab",
        "alt+shift+tab",
        "ctrl+alt+tab",
        "alt+escape",
        "alt+f4",
        "alt+space",
        "ctrl+alt+backspace",
        # Edição de texto e janelas: em qualquer programa.
        "ctrl+a",
        "ctrl+c",
        "ctrl+v",
        "ctrl+x",
        "ctrl+z",
        "ctrl+y",
        "ctrl+s",
        "ctrl+f",
        "ctrl+p",
        "ctrl+w",
        "ctrl+t",
        "ctrl+n",
        "ctrl+o",
        "ctrl+shift+z",
        "ctrl+shift+t",
        "ctrl+shift+n",
        "ctrl+tab",
        "ctrl+shift+tab",
        "ctrl+f4",
    }
    # Win + letra/tecla: quase todas são do Windows (Win+L bloqueia, Win+D
    # mostra a área de trabalho...).
    | {
        f"win+{tecla}"
        for tecla in (
            "l d e r i a s v p g h k m u x b c n o q t w z tab space "
            "up down left right home pause enter escape "
            "1 2 3 4 5 6 7 8 9 0"
        ).split()
    }
    # Sempre na ordem canônica (ctrl, alt, shift, win).
    | {"ctrl+win+d", "ctrl+win+left", "ctrl+win+right", "ctrl+win+f4"}
    | {"shift+win+s", "shift+win+left", "shift+win+right"}
)


class CombinacaoInvalida(ValueError):
    """A combinação não serve para atalho global (mensagem em português)."""


@dataclass(frozen=True, slots=True)
class Combinacao:
    """Uma combinação já validada."""

    modificadores: tuple[str, ...]
    tecla: str

    @property
    def texto(self) -> str:
        """Forma gravada no config: ``"ctrl+alt+n"``."""
        return "+".join((*self.modificadores, self.tecla))

    @property
    def rotulo(self) -> str:
        """Forma mostrada ao usuário: ``"Ctrl + Alt + N"``."""
        partes = [_NOMES_MODIFICADORES[m] for m in self.modificadores]
        partes.append(nome_da_tecla(self.tecla))
        return " + ".join(partes)

    @property
    def bits_modificadores(self) -> int:
        bits = 0
        for mod in self.modificadores:
            bits |= MODIFICADORES[mod]
        return bits

    @property
    def codigo_virtual(self) -> int:
        return codigo_virtual(self.tecla)


def nome_da_tecla(tecla: str) -> str:
    if tecla in _NOMES_ESPECIAIS:
        return _NOMES_ESPECIAIS[tecla]
    return tecla.upper()


def _tecla_valida(tecla: str) -> bool:
    if len(tecla) == 1 and (tecla.isascii() and tecla.isalnum()):
        return True
    if tecla in _TECLAS_ESPECIAIS:
        return True
    return tecla.startswith("f") and tecla[1:].isdigit() and 1 <= int(tecla[1:]) <= 24


def codigo_virtual(tecla: str) -> int:
    """Código virtual (VK_*) do Windows para *tecla* já normalizada."""
    if len(tecla) == 1:
        return ord(tecla.upper())  # VK de A-Z e 0-9 = código ASCII maiúsculo
    if tecla in _TECLAS_ESPECIAIS:
        return _TECLAS_ESPECIAIS[tecla]
    return 0x70 + int(tecla[1:]) - 1  # VK_F1 = 0x70


def ler_combinacao(texto: str) -> Combinacao:
    """Lê e valida *texto* (``"Ctrl + Alt + N"``, ``"ctrl+alt+n"``...).

    Levanta :class:`CombinacaoInvalida` com a explicação em português.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise CombinacaoInvalida("Escolha uma combinação de teclas.")
    partes = [p.strip().lower() for p in texto.replace(" ", "").split("+")]
    if any(not p for p in partes):
        raise CombinacaoInvalida(f"Combinação mal escrita: {texto!r}.")
    partes = [_SINONIMOS.get(p, p) for p in partes]

    mods = {p for p in partes if p in MODIFICADORES}
    teclas = [p for p in partes if p not in MODIFICADORES]
    if len(mods) != len([p for p in partes if p in MODIFICADORES]):
        raise CombinacaoInvalida("Um modificador apareceu repetido.")
    if not teclas:
        raise CombinacaoInvalida(
            "Falta a tecla principal: use modificadores e uma tecla "
            "(ex.: Ctrl + Alt + N)."
        )
    if len(teclas) > 1:
        raise CombinacaoInvalida("Use só uma tecla além dos modificadores.")
    tecla = teclas[0]
    if not _tecla_valida(tecla):
        raise CombinacaoInvalida(f"Tecla não suportada no atalho: {tecla!r}.")
    if not mods & {"ctrl", "alt", "win"}:
        raise CombinacaoInvalida(
            "O atalho precisa de Ctrl, Alt ou Win (só Shift atrapalharia a digitação)."
        )

    combinacao = Combinacao(tuple(m for m in MODIFICADORES if m in mods), tecla)
    if combinacao.texto in RESERVADAS:
        raise CombinacaoInvalida(
            f"{combinacao.rotulo} é do sistema ou de uso geral; escolha outra."
        )
    return combinacao


def normalizar(texto: str) -> str:
    """Forma canônica de *texto* (valida no caminho)."""
    return ler_combinacao(texto).texto


__all__ = [
    "MODIFICADORES",
    "RESERVADAS",
    "Combinacao",
    "CombinacaoInvalida",
    "codigo_virtual",
    "ler_combinacao",
    "nome_da_tecla",
    "normalizar",
]
