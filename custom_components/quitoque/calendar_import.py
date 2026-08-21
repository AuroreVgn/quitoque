"""Import Quitoque recipes into a writable Home Assistant calendar."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging
from typing import Any, Iterable

from homeassistant.core import HomeAssistant

from .const import MARKER_PREFIX
from .models import QuitoqueOrder, QuitoqueRecipe

_LOGGER = logging.getLogger(__name__)

_EVENT_DURATION_MINUTES = 60
_EVENT_START_SLOTS = (time(hour=8), time(hour=9), time(hour=10))
_WEEK_MARKER_PREFIX = f"{MARKER_PREFIX}_WEEK"
_DELIVERY_MARKER_PREFIX = f"{MARKER_PREFIX}_DELIVERY"


async def async_import_orders(
    hass: HomeAssistant,
    calendar_entity_id: str,
    orders: Iterable[QuitoqueOrder],
    event_prefix: str = "",
) -> int:
    """Import all not-yet-imported weeks and return the event count created."""
    created = 0
    for order in sorted(orders, key=lambda item: item.delivery_date):
        created += await async_import_order(
            hass,
            calendar_entity_id,
            order,
            event_prefix,
        )
    return created


async def async_import_order(
    hass: HomeAssistant,
    calendar_entity_id: str,
    order: QuitoqueOrder,
    event_prefix: str = "",
) -> int:
    """Import missing delivery and recipe events for one Quitoque week."""
    events = await _async_existing_events(hass, calendar_entity_id, order)
    recipes_already_imported = _week_already_imported_in_events(events, order)
    delivery_already_imported = _delivery_already_imported_in_events(events, order)

    created = 0
    week_number = order.delivery_date.isocalendar().week
    week_marker = _week_marker(order)
    prefix = event_prefix.strip()
    prefix_part = f"{prefix} " if prefix else ""

    if not delivery_already_imported:
        await hass.services.async_call(
            "calendar",
            "create_event",
            {
                "summary": _delivery_summary(
                    order,
                    week_number,
                    prefix_part,
                ),
                "description": "\n".join(
                    [
                        f"Livraison Quitoque du {order.delivery_date.strftime('%d/%m/%Y')}",
                        f"Créneau de livraison : {_delivery_time_range(order)}",
                        order.recipes_url,
                        _delivery_marker(order),
                    ]
                ),
                "start_date": order.delivery_date.isoformat(),
                "end_date": (order.delivery_date + timedelta(days=1)).isoformat(),
            },
            target={"entity_id": calendar_entity_id},
            blocking=True,
        )
        created += 1

    if recipes_already_imported:
        _LOGGER.debug(
            "Semaine Quitoque déjà importée, recettes non recréées : %s-W%02d",
            order.delivery_date.isocalendar().year,
            week_number,
        )
        return created

    for index, recipe in enumerate(order.recipes):
        marker = _marker(order, recipe)
        slot = _EVENT_START_SLOTS[index % len(_EVENT_START_SLOTS)]
        start_datetime = datetime.combine(order.delivery_date, slot)
        end_datetime = start_datetime + timedelta(minutes=_EVENT_DURATION_MINUTES)

        duration = (
            f"{recipe.duration_minutes} min"
            if recipe.duration_minutes is not None
            else "durée inconnue"
        )

        await hass.services.async_call(
            "calendar",
            "create_event",
            {
                "summary": (
                    f"{prefix_part}S{week_number:02d} - "
                    f"{recipe.name} — {duration}"
                ),
                "description": _description(order, recipe, marker, week_marker),
                "start_date_time": start_datetime.isoformat(),
                "end_date_time": end_datetime.isoformat(),
            },
            target={"entity_id": calendar_entity_id},
            blocking=True,
        )
        created += 1

    _LOGGER.debug(
        "Semaine Quitoque importée : %s (%s événements créés)",
        order.delivery_date.isoformat(),
        created,
    )
    return created


def _week_already_imported_in_events(
    events: list[dict[str, Any]],
    order: QuitoqueOrder,
) -> bool:
    """Return True if recipe events for this week already exist."""
    week_marker = _week_marker(order)
    legacy_delivery_line = f"Livraison : {order.delivery_date.strftime('%d/%m/%Y')}"

    for event in events:
        description = str(event.get("description", ""))
        lines = {line.strip() for line in description.splitlines()}

        if week_marker in lines:
            return True

        if (
            legacy_delivery_line in lines
            and any(line.startswith(MARKER_PREFIX + ":") for line in lines)
        ):
            return True

    return False


def _delivery_already_imported_in_events(
    events: list[dict[str, Any]],
    order: QuitoqueOrder,
) -> bool:
    """Return True if the all-day delivery event already exists."""
    marker = _delivery_marker(order)
    for event in events:
        description = str(event.get("description", ""))
        if marker in {line.strip() for line in description.splitlines()}:
            return True
    return False


async def _async_existing_events(
    hass: HomeAssistant,
    calendar_entity_id: str,
    order: QuitoqueOrder,
) -> list[dict[str, Any]]:
    """Read calendar events for the full delivery year.

    The Quitoque events may have been manually moved to another day after
    import. Searching the whole year keeps the week-level duplicate detection
    effective even when the recipes are reorganized in the calendar.
    """
    # Search the previous, current and following calendar year. The marker
    # itself contains the ISO year + ISO week, so W01/W52/W53 from different
    # years can never be confused. The wider window also keeps duplicate
    # detection working when the user moves a recipe across New Year's Day.
    start = order.delivery_date.replace(
        year=order.delivery_date.year - 1,
        month=1,
        day=1,
    )
    end = order.delivery_date.replace(
        year=order.delivery_date.year + 1,
        month=12,
        day=31,
    )

    try:
        response: Any = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "start_date_time": f"{start.isoformat()} 00:00:00",
                "end_date_time": f"{end.isoformat()} 23:59:59",
            },
            target={"entity_id": calendar_entity_id},
            blocking=True,
            return_response=True,
        )
    except Exception:
        _LOGGER.debug(
            "Impossible de lire les événements existants du calendrier %s",
            calendar_entity_id,
            exc_info=True,
        )
        # Do NOT report the week as imported when verification failed.
        # This lets the service surface its normal create_event errors rather
        # than silently skipping an import.
        return []

    if not isinstance(response, dict):
        return []

    entity_data = response.get(calendar_entity_id, response)
    if isinstance(entity_data, dict):
        candidate = entity_data.get("events", [])
        return candidate if isinstance(candidate, list) else []
    if isinstance(entity_data, list):
        return entity_data
    return []


def _week_marker(order: QuitoqueOrder) -> str:
    iso = order.delivery_date.isocalendar()
    return f"{_WEEK_MARKER_PREFIX}:{iso.year}:W{iso.week:02d}"


def _delivery_marker(order: QuitoqueOrder) -> str:
    iso = order.delivery_date.isocalendar()
    return f"{_DELIVERY_MARKER_PREFIX}:{iso.year}:W{iso.week:02d}"


def _marker(order: QuitoqueOrder, recipe: QuitoqueRecipe) -> str:
    return f"{MARKER_PREFIX}:{order.order_id}:{recipe.item_id}"


def _delivery_summary(
    order: QuitoqueOrder,
    week_number: int,
    prefix_part: str,
) -> str:
    """Return the all-day delivery event title including its time slot."""
    return (
        f"{prefix_part}S{week_number:02d} - Livraison Quitoque "
        f"- {_delivery_time_range(order)}"
    )


def _delivery_time_range(order: QuitoqueOrder) -> str:
    """Return the delivery time slot in a human-readable form."""
    if (
        order.delivery_start_hour is None
        or order.delivery_end_hour is None
    ):
        return "horaire non communiqué"

    return (
        f"{order.delivery_start_hour:02d}h00 - "
        f"{order.delivery_end_hour:02d}h00"
    )


def _description(
    order: QuitoqueOrder,
    recipe: QuitoqueRecipe,
    marker: str,
    week_marker: str,
) -> str:
    category = "Recette" if recipe.category == "recipe" else "Kit"
    duration = (
        f"{recipe.duration_minutes} min"
        if recipe.duration_minutes is not None
        else "inconnue"
    )
    return "\n".join(
        [
            f"{category} Quitoque — quantité : {recipe.quantity}",
            f"Durée : {duration}",
            f"Livraison : {order.delivery_date.strftime('%d/%m/%Y')}",
            f"Créneau de livraison : {_delivery_time_range(order)}",
            order.recipes_url,
            week_marker,
            marker,
        ]
    )
