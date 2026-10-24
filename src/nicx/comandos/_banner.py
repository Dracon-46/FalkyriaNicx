"""Startup banner — Nicx wordmark + tagline."""

from __future__ import annotations

# "Nicx" rendered in the figlet "standard" font (letters kept unsmushed so
# each glyph stays legible). Stored as plain text (no inline Rich markup) so
# the backslashes in the glyphs don't collide with Rich's [tag] markup or
# Python raw-string escaping — colour is applied at print time via a style
# argument.
_WORDMARK = (
    " _   _   _               ",
    "| \\ | | (_)   ___  __  __",
    "|  \\| | | |  / __| \\ \\/ /",
    "| |\\  | | | | (__   >  < ",
    "|_| \\_| |_|  \\___| /_/\\_\\",
)

_TAGLINE = "A inteligência artificial da Falkyria"

# Falkyria palette: off-white wordmark, amber signature accent.
_WORDMARK_STYLE = "bold #fcfcfb"
_TAGLINE_STYLE = "#eda100"


def print_banner(quiet: bool = False) -> None:
    """Print the Nicx startup banner. No-op when quiet."""
    if quiet:
        return
    try:
        from rich.console import Console

        console = Console()
        for line in _WORDMARK:
            console.print(line, style=_WORDMARK_STYLE, highlight=False, markup=False)
        console.print(
            f"  {_TAGLINE}", style=_TAGLINE_STYLE, highlight=False, markup=False
        )
        console.print()
    except ImportError:
        for line in _WORDMARK:
            print(line)
        print(f"  {_TAGLINE}")
        print()
