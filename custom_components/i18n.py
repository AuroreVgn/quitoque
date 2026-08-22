"""Small runtime localization helpers for Quitoque."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


def is_french(hass: HomeAssistant) -> bool:
    """Return True when Home Assistant is configured in French."""
    return (hass.config.language or "en").lower().startswith("fr")


def localize(hass: HomeAssistant, french: str, english: str) -> str:
    """Return a French/English runtime string."""
    return french if is_french(hass) else english
