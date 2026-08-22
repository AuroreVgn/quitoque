"""Quitoque data update coordinator."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import QuitoqueAuthenticationError, QuitoqueClient, QuitoqueError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .metadata import (
    async_get_recipe_card_metadata,
    async_resolve_recipe_catalogue_metadata,
)
from .models import QuitoqueOrder
from .history_images import async_history_recipe_metadata

_LOGGER = logging.getLogger(__name__)


class QuitoqueCoordinator(DataUpdateCoordinator[QuitoqueOrder | None]):
    """Coordinate Quitoque updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: QuitoqueClient,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
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

        self.recipe_metadata: dict[tuple[int, int], dict[str, Any]] = {}
        self._recipe_store: Store[dict[str, Any]] = Store(
            hass,
            1,
            f"{DOMAIN}_{entry.entry_id}_recipe_metadata",
        )
        self._recipe_cache_loaded = False
        self.client.set_auth_event_callback(self._handle_auth_event)

    async def _async_load_recipe_cache(self) -> None:
        """Load persistent recipe metadata once after Home Assistant starts."""
        if self._recipe_cache_loaded:
            return

        self._recipe_cache_loaded = True
        stored = await self._recipe_store.async_load()
        if not isinstance(stored, dict):
            return

        items = stored.get("recipes", {})
        if not isinstance(items, dict):
            return

        for raw_key, metadata in items.items():
            if not isinstance(raw_key, str) or ":" not in raw_key:
                continue
            if not isinstance(metadata, dict):
                continue
            try:
                order_id, item_id = (int(value) for value in raw_key.split(":", 1))
            except ValueError:
                continue
            self.recipe_metadata[(order_id, item_id)] = metadata

        if self.recipe_metadata:
            _LOGGER.debug(
                "Cache persistant Quitoque chargé : %s recette(s)",
                len(self.recipe_metadata),
            )

    async def _async_save_recipe_cache(self) -> None:
        """Persist current recipe metadata for the next HA restart."""
        payload = {
            "recipes": {
                f"{order_id}:{item_id}": metadata
                for (order_id, item_id), metadata in self.recipe_metadata.items()
                if metadata.get("_complete")
            }
        }
        await self._recipe_store.async_save(payload)

    def _handle_auth_event(self, event: str) -> None:
        """Record successful Quitoque authentication events."""
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

        self.async_update_listeners()

    async def _async_update_recipe_metadata(
        self,
        orders: tuple[QuitoqueOrder, ...],
    ) -> None:
        """Populate lightweight metadata for all currently exposed recipes."""
        await self._async_load_recipe_cache()
        active_keys: set[tuple[int, int]] = set()

        recipes_needing_metadata = [
            recipe.name
            for order in orders
            for recipe in order.recipes
            if not self.recipe_metadata.get(
                (order.order_id, recipe.item_id), {}
            ).get("_complete")
        ]
        catalogue_metadata = await async_resolve_recipe_catalogue_metadata(
            self.client,
            recipes_needing_metadata,
        )
        if catalogue_metadata:
            _LOGGER.debug(
                "Métadonnées catalogue Quitoque résolues : %s",
                catalogue_metadata,
            )

        history_metadata = await async_history_recipe_metadata(
            self.client,
            orders,
        )
        if history_metadata:
            image_count = sum(
                1 for value in history_metadata.values()
                if value.get("image_url")
            )
            url_count = sum(
                1 for value in history_metadata.values()
                if value.get("detail_url")
            )
            _LOGGER.debug(
                "Métadonnées historiques Quitoque : images=%s urls=%s",
                image_count,
                url_count,
            )

        unresolved_names = [
            name
            for name in recipes_needing_metadata
            if name not in catalogue_metadata
        ]
        if unresolved_names:
            _LOGGER.debug(
                "Recettes Quitoque sans URL catalogue résolue : %s",
                unresolved_names,
            )

        for order in orders:
            for recipe in order.recipes:
                key = (order.order_id, recipe.item_id)
                active_keys.add(key)

                cached = self.recipe_metadata.get(key)
                if cached and cached.get("_complete"):
                    continue

                try:
                    history = history_metadata.get(
                        (order.order_id, recipe.item_id),
                        {},
                    )

                    # Future boxes already expose exact /products URLs through
                    # recipe.detail_url. Historical boxes can now recover the
                    # same URL from their history card.
                    product_url = history.get("detail_url")
                    if not product_url and recipe.detail_url and "/products/" in recipe.detail_url:
                        product_url = recipe.detail_url

                    metadata = await async_get_recipe_card_metadata(
                        self.client,
                        recipe,
                        detail_url=(
                            catalogue_metadata.get(recipe.name, {}).get(
                                "detail_url"
                            )
                        ),
                        product_url=product_url,
                    )

                    catalogue = catalogue_metadata.get(recipe.name, {})

                    history_image = history.get("image_url")
                    if not metadata.get("image_url") and history_image:
                        metadata["image_url"] = history_image

                    # The catalogue card is authoritative for the displayed
                    # total duration and is a useful image fallback. Product
                    # order pages often expose only the kitchen duration.
                    if catalogue.get("total_duration_minutes") is not None:
                        metadata["total_duration_minutes"] = catalogue[
                            "total_duration_minutes"
                        ]
                    if (
                        not metadata.get("image_url")
                        and catalogue.get("image_url")
                    ):
                        metadata["image_url"] = catalogue["image_url"]
                except QuitoqueAuthenticationError:
                    raise
                except Exception as err:
                    _LOGGER.debug(
                        "Métadonnées carte Quitoque indisponibles pour %s : %s",
                        recipe.name,
                        err,
                        exc_info=True,
                    )
                    self.recipe_metadata[key] = {
                        "name": recipe.name,
                        "total_duration_minutes": None,
                        "kitchen_duration_minutes": recipe.duration_minutes,
                        "servings": None,
                        "image_url": None,
                        "_complete": False,
                    }
                    continue

                metadata["_complete"] = True
                self.recipe_metadata[key] = metadata

                _LOGGER.debug(
                    "Métadonnées carte Quitoque : recette=%s total=%s cuisine=%s "
                    "portions=%s image=%s",
                    recipe.name,
                    metadata.get("total_duration_minutes"),
                    metadata.get("kitchen_duration_minutes"),
                    metadata.get("servings"),
                    bool(metadata.get("image_url")),
                )

        for key in tuple(self.recipe_metadata):
            if key not in active_keys:
                self.recipe_metadata.pop(key, None)

        await self._async_save_recipe_cache()

    async def _async_update_data(self) -> QuitoqueOrder | None:
        try:
            self.orders = await self.client.async_get_orders()
            await self._async_update_recipe_metadata(self.orders)
            return self.orders[0] if self.orders else None
        except QuitoqueAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QuitoqueError as err:
            raise UpdateFailed(str(err)) from err
