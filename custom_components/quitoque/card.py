"""Serve the bundled Quitoque Lovelace card and register its resource."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig

_LOGGER = logging.getLogger(__name__)
CARD_URL = "/quitoque/quitoque-card.js"
CARD_FILE = Path(__file__).parent / "www" / "quitoque-card.js"


async def async_setup_card(hass) -> None:
    """Register the card once, without altering existing user resources."""
    if hass.data.get("quitoque_card_registered"):
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    hass.data["quitoque_card_registered"] = True

    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.info(
            "Quitoque card is available at %s; add it manually as a dashboard resource",
            CARD_URL,
        )
        return

    try:
        if not resources.loaded:
            await resources.async_load()
        if any(
            item.get("url", "").split("?")[0] == CARD_URL
            for item in resources.async_items()
        ):
            return
        await resources.async_create_item(
            {"res_type": "module", "url": CARD_URL}
        )
    except Exception:
        _LOGGER.exception(
            "Unable to auto-register Quitoque card resource; add %s manually",
            CARD_URL,
        )
