"""Recipe system — composable primitive configurations."""

from nicx.cerebro.receitas.composer import (
    recipe_to_operator,
)
from nicx.cerebro.receitas.loader import (
    Recipe,
    discover_recipes,
    load_recipe,
    resolve_recipe,
)

__all__ = [
    "Recipe",
    "discover_recipes",
    "load_recipe",
    "recipe_to_operator",
    "resolve_recipe",
]
