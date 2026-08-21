"""Quitoque data update coordinator."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import QuitoqueAuthenticationError, QuitoqueClient, QuitoqueError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import QuitoqueOrder


class QuitoqueCoordinator(DataUpdateCoordinator[QuitoqueOrder | None]):
    """Coordinate Quitoque updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: QuitoqueClient) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.orders: tuple[QuitoqueOrder, ...] = ()
        self.operation_in_progress = False

    async def _async_update_data(self) -> QuitoqueOrder | None:
        try:
            self.orders = await self.client.async_get_orders()
            return self.orders[0] if self.orders else None
        except QuitoqueAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QuitoqueError as err:
            raise UpdateFailed(str(err)) from err
