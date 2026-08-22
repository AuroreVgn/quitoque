"""Diagnostics support for Quitoque."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import QuitoqueConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QuitoqueConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostics for one Quitoque entry."""
    order = entry.runtime_data.coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "authentication": {
            "session_authenticated": entry.runtime_data.coordinator.client._authenticated,
            "last_successful_login": (
                entry.runtime_data.coordinator.last_successful_login.isoformat()
                if entry.runtime_data.coordinator.last_successful_login is not None
                else None
            ),
            "last_auto_reconnect": (
                entry.runtime_data.coordinator.last_auto_reconnect.isoformat()
                if entry.runtime_data.coordinator.last_auto_reconnect is not None
                else None
            ),
        },
        "order": asdict(order) if order is not None else None,
    }
