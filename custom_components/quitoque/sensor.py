"""Sensors for Quitoque."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import QuitoqueConfigEntry
from .entity import QuitoqueEntity
from .i18n import localize


async def async_setup_entry(
    hass, entry: QuitoqueConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            QuitoqueWeekDeliverySensor(entry, 0),
            QuitoqueWeekDeliverySensor(entry, 1),
            QuitoqueWeekDeliverySensor(entry, 2),
            QuitoqueWeekDeliverySensor(entry, 3),
            QuitoqueWeekDeliverySensor(entry, 4),
            QuitoqueWeekRecipeCountSensor(entry, 0),
            QuitoqueWeekRecipeCountSensor(entry, 1),
            QuitoqueWeekRecipeCountSensor(entry, 2),
            QuitoqueWeekRecipeCountSensor(entry, 3),
            QuitoqueWeekRecipeCountSensor(entry, 4),
            QuitoqueLastActionSensor(entry, "last_calendar_sync"),
            QuitoqueLastActionSensor(entry, "last_pdf_generation"),
            QuitoqueLastActionSensor(entry, "last_successful_login"),
            QuitoqueLastActionSensor(entry, "last_auto_reconnect"),
            QuitoqueLastTextSensor(entry, "last_status", "never"),
            QuitoqueLastTextSensor(entry, "last_error", "none"),
        ]
    )


def _week_bounds(week_offset: int) -> tuple[date, date]:
    """Return Monday/Sunday for a week relative to the current week."""
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    monday = current_monday + timedelta(weeks=week_offset)
    return monday, monday + timedelta(days=6)


def _order_for_week(coordinator, week_offset: int):
    """Return the active order whose delivery falls in the requested week."""
    monday, sunday = _week_bounds(week_offset)
    for order in coordinator.orders:
        if monday <= order.delivery_date <= sunday:
            return order
    return None


class QuitoqueWeekDeliverySensor(QuitoqueEntity, SensorEntity):
    """Delivery date for one managed calendar week (S0 through S+4)."""

    _attr_icon = "mdi:truck-delivery"

    def __init__(self, entry: QuitoqueConfigEntry, week_offset: int) -> None:
        super().__init__(entry)
        self._week_offset = week_offset
        self._attr_translation_key = f"delivery_week_{week_offset}"
        self._attr_unique_id = f"{entry.entry_id}_delivery_week_{week_offset}"

    @property
    def native_value(self):
        order = _order_for_week(self.coordinator, self._week_offset)
        if order is not None:
            return order.delivery_date.isoformat()
        return localize(self.hass, "Non", "No")

    @property
    def extra_state_attributes(self):
        monday, sunday = _week_bounds(self._week_offset)
        order = _order_for_week(self.coordinator, self._week_offset)
        iso = monday.isocalendar()

        attrs = {
            "week": iso.week,
            "iso_year": iso.year,
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "active_delivery": order is not None,
        }
        if order is None:
            attrs.update(
                {
                    "order_id": None,
                    "delivery_start_hour": None,
                    "delivery_end_hour": None,
                    "recipes_url": None,
                }
            )
            return attrs

        attrs.update(
            {
                "order_id": order.order_id,
                "delivery_start_hour": order.delivery_start_hour,
                "delivery_end_hour": order.delivery_end_hour,
                "recipes_url": order.recipes_url,
            }
        )
        return attrs


class QuitoqueWeekRecipeCountSensor(QuitoqueEntity, SensorEntity):
    """Recipe count for one managed calendar week (S0 through S+4)."""

    _attr_icon = "mdi:food-variant"
    @property
    def native_unit_of_measurement(self) -> str:
        """Return the localized recipe unit."""
        return localize(self.hass, "recettes", "recipes")

    def __init__(self, entry: QuitoqueConfigEntry, week_offset: int) -> None:
        super().__init__(entry)
        self._week_offset = week_offset
        self._attr_translation_key = f"recipe_count_week_{week_offset}"
        self._attr_unique_id = f"{entry.entry_id}_recipe_count_week_{week_offset}"

    @property
    def native_value(self):
        order = _order_for_week(self.coordinator, self._week_offset)
        return len(order.recipes) if order is not None else 0

    @property
    def extra_state_attributes(self):
        monday, sunday = _week_bounds(self._week_offset)
        order = _order_for_week(self.coordinator, self._week_offset)
        iso = monday.isocalendar()
        return {
            "week": iso.week,
            "iso_year": iso.year,
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "delivery_date": (
                order.delivery_date.isoformat() if order is not None else None
            ),
            "recipes": (
                [recipe.name for recipe in order.recipes]
                if order is not None
                else []
            ),
        }


class QuitoqueLastActionSensor(QuitoqueEntity, SensorEntity, RestoreEntity):
    """Persistent timestamp of a successful Quitoque user action."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, entry: QuitoqueConfigEntry, action_key: str) -> None:
        super().__init__(entry)
        self._action_key = action_key
        self._attr_translation_key = action_key
        self._attr_unique_id = f"{entry.entry_id}_{action_key}"
        self._attr_native_value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the timestamp after a Home Assistant restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable", "none"):
            try:
                self._attr_native_value = datetime.fromisoformat(last_state.state)
            except ValueError:
                self._attr_native_value = None

        coordinator_value = getattr(self.coordinator, self._action_key, None)
        if coordinator_value is not None and (
            self._attr_native_value is None
            or coordinator_value > self._attr_native_value
        ):
            self._attr_native_value = coordinator_value

        registry = self.hass.data.setdefault("quitoque_action_sensors", {})
        registry[(self._entry.entry_id, self._action_key)] = self

    async def async_will_remove_from_hass(self) -> None:
        self.hass.data.get("quitoque_action_sensors", {}).pop(
            (self._entry.entry_id, self._action_key), None
        )
        await super().async_will_remove_from_hass()

    def set_value(self, value: datetime) -> None:
        """Set and persist a new action timestamp."""
        self._attr_native_value = value
        self.async_write_ha_state()



class QuitoqueLastTextSensor(QuitoqueEntity, SensorEntity, RestoreEntity):
    """Persistent text diagnostic value."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:information-outline"

    def __init__(
        self,
        entry: QuitoqueConfigEntry,
        action_key: str,
        default_value: str,
    ) -> None:
        super().__init__(entry)
        self._action_key = action_key
        self._default_value = default_value
        self._attr_translation_key = action_key
        self._attr_unique_id = f"{entry.entry_id}_{action_key}"
        self._attr_native_value = default_value

    async def async_added_to_hass(self) -> None:
        """Restore the value after a Home Assistant restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            "unknown",
            "unavailable",
        ):
            restored = last_state.state

            # Migrate values stored by earlier releases.
            if self._action_key == "last_status":
                restored = {
                    "Jamais": "never",
                    "Aucune action": "never",
                    "Succès": "success",
                    "Erreur": "error",
                    "Aucune livraison": "no_delivery",
                }.get(restored, restored)
            elif self._action_key == "last_error":
                restored = {
                    "Aucune": "none",
                    "None": "none",
                }.get(restored, restored)

            self._attr_native_value = restored

        registry = self.hass.data.setdefault("quitoque_action_sensors", {})
        registry[(self._entry.entry_id, self._action_key)] = self

    async def async_will_remove_from_hass(self) -> None:
        self.hass.data.get("quitoque_action_sensors", {}).pop(
            (self._entry.entry_id, self._action_key), None
        )
        await super().async_will_remove_from_hass()

    @property
    def native_value(self):
        """Return localized diagnostic values while storing canonical tokens."""
        value = self._attr_native_value

        if self._action_key == "last_status":
            labels = {
                "never": ("Aucune action", "No action yet"),
                "success": ("Succès", "Success"),
                "error": ("Erreur", "Error"),
                "no_delivery": ("Aucune livraison", "No delivery"),
            }
            if value in labels:
                fr, en = labels[value]
                return localize(self.hass, fr, en)

        if self._action_key == "last_error" and value == "none":
            return localize(self.hass, "Aucune", "None")

        return value

    def set_value(self, value: str) -> None:
        """Set and persist a diagnostic text value."""
        self._attr_native_value = str(value)[:255]
        self.async_write_ha_state()
