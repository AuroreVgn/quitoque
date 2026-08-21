"""Base entity for Quitoque."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QuitoqueConfigEntry
from .const import DOMAIN
from .coordinator import QuitoqueCoordinator


class QuitoqueEntity(CoordinatorEntity[QuitoqueCoordinator]):
    """Base Quitoque entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: QuitoqueConfigEntry) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Quitoque",
            model="Box repas",
        )
