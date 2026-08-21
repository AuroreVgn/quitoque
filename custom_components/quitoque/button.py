"""Buttons for Quitoque."""

from __future__ import annotations

import time

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QuitoqueConfigEntry
from .actions import (
    async_generate_pdfs,
    async_refresh,
    async_sync_calendar,
    managed_orders,
)
from .entity import QuitoqueEntity


async def async_setup_entry(
    hass, entry: QuitoqueConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            QuitoqueRefreshButton(entry),
            QuitoqueSyncButton(entry),
            QuitoquePdfButton(entry),
        ]
    )


class QuitoqueRefreshButton(QuitoqueEntity, ButtonEntity):
    """Refresh Quitoque data without reloading the integration."""

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, entry: QuitoqueConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh"

    @property
    def available(self) -> bool:
        return super().available and not self.coordinator.operation_in_progress

    async def async_press(self) -> None:
        await async_refresh(self._entry)


class QuitoqueSyncButton(QuitoqueEntity, ButtonEntity):
    """Import S+2/S+3/S+4 recipes into the calendar."""

    _attr_translation_key = "sync_calendar"
    _attr_icon = "mdi:calendar-import"

    def __init__(self, entry: QuitoqueConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_sync_calendar"

    @property
    def available(self) -> bool:
        return (
            super().available
            and not self.coordinator.operation_in_progress
            and bool(managed_orders(self._entry))
        )

    async def async_press(self) -> None:
        await async_sync_calendar(self._entry)


class QuitoquePdfButton(QuitoqueEntity, ButtonEntity):
    """Generate printable PDFs for S+2/S+3/S+4 recipes."""

    _attr_translation_key = "export_pdf"
    _attr_icon = "mdi:file-pdf-box"

    def __init__(self, entry: QuitoqueConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_export_pdf"

    @property
    def available(self) -> bool:
        return (
            super().available
            and not self.coordinator.operation_in_progress
            and bool(managed_orders(self._entry))
        )

    async def async_press(self) -> None:
        result = await async_generate_pdfs(self._entry)

        version_token = time.time_ns()
        generated = result["generated"]
        errors = result["errors"]
        archive_url = result["archive_url"]

        links = "<br>".join(
            f'<a href="{url}?v={version_token}" target="_blank" download>{name}</a>'
            for name, url in generated
        )

        message = f"{len(generated)} PDF de recette(s) généré(s)."
        if archive_url:
            message += (
                f'<br><br><a href="{archive_url}" target="_blank" download>'
                "Télécharger toutes les recettes (.zip)</a>"
            )
        if links:
            message += f"<br><br>Téléchargements individuels :<br>{links}"
        if errors:
            message += "<br><br>Recettes non exportées :<br>" + "<br>".join(errors)

        persistent_notification.async_create(
            self.hass,
            message,
            title="PDF Quitoque prêts",
            notification_id="quitoque_recipes_pdf",
        )
