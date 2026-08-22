"""Quitoque data update coordinator."""

from __future__ import annotations

from datetime import datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
        self._entry = entry
        self.orders: tuple[QuitoqueOrder, ...] = ()
        self.operation_in_progress = False
        self.last_successful_login: datetime | None = None
        self.last_auto_reconnect: datetime | None = None
        self.client.set_auth_event_callback(self._handle_auth_event)

    def _handle_auth_event(self, event: str) -> None:
        """Record successful Quitoque authentication events.

        The API client calls this synchronously after a successful login.
        Values are kept in the coordinator until the diagnostic entities are
        loaded, then written to their RestoreEntity sensors.
        """
        now = dt_util.utcnow()

        if event == "login_success":
            self.last_successful_login = now
            action_key = "last_successful_login"
        elif event == "auto_reconnect":
            self.last_auto_reconnect = now
            action_key = "last_auto_reconnect"
        else:
            return

        sensor = self.hass.data.get("quitoque_action_sensors", {}).get(
            (self._entry.entry_id, action_key)
        )
        if sensor is not None:
            sensor.set_value(now)

        # Refresh entities that may expose coordinator-backed diagnostics.
        self.async_update_listeners()

    async def _async_update_data(self) -> QuitoqueOrder | None:
        try:
            self.orders = await self.client.async_get_orders()
            return self.orders[0] if self.orders else None
        except QuitoqueAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QuitoqueError as err:
            raise UpdateFailed(str(err)) from err
