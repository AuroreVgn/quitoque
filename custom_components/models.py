"""Data models for Quitoque."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class QuitoqueRecipe:
    """A recipe present in a Quitoque order."""

    item_id: int
    name: str
    category: str
    quantity: int
    price_cents: int | None = None
    duration_minutes: int | None = None
    detail_url: str | None = None


@dataclass(frozen=True, slots=True)
class QuitoqueOrder:
    """A Quitoque order extracted from the recipes page."""

    order_id: int
    delivery_date: date
    delivery_start_hour: int | None
    delivery_end_hour: int | None
    recipes_url: str
    recipes: tuple[QuitoqueRecipe, ...]



@dataclass(frozen=True, slots=True)
class QuitoqueRecipeStep:
    """One preparation step of a Quitoque recipe."""

    number: int
    title: str
    instructions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QuitoqueRecipeDetails:
    """Detailed preparation instructions for a Quitoque recipe."""

    name: str
    duration_minutes: int | None
    source_url: str
    image_url: str | None
    steps: tuple[QuitoqueRecipeStep, ...]
    ingredients: tuple[str, ...] = ()
    kitchen_ingredients: tuple[str, ...] = ()
    equipment: tuple[str, ...] = ()
    servings: str | None = None
