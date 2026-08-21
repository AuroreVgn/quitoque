"""The Quitoque integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientSession, CookieJar
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .actions import (
    async_delete_recipes_archive,
    async_cleanup_pdfs,
    async_generate_pdfs,
    async_refresh,
    async_sync_calendar,
)
from .api import QuitoqueClient
from .i18n import localize
from .const import (
    CONF_PDF_RETENTION_DAYS,
    CONF_RECIPES_URL,
    DEFAULT_PDF_RETENTION_DAYS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import QuitoqueCoordinator
from .pdf_export import cleanup_expired_recipe_pdfs


_LOGGER = logging.getLogger(__name__)
_PDF_CLEANUP_INTERVAL = timedelta(hours=12)


@dataclass(slots=True)
class QuitoqueRuntimeData:
    """Runtime data for one Quitoque config entry."""

    coordinator: QuitoqueCoordinator
    session: ClientSession


type QuitoqueConfigEntry = ConfigEntry[QuitoqueRuntimeData]


SERVICE_REFRESH = "refresh"
SERVICE_SYNC_CALENDAR = "sync_calendar"
SERVICE_GENERATE_PDFS = "generate_pdfs"
SERVICE_CLEANUP_PDFS = "cleanup_pdfs"
SERVICE_DELETE_ARCHIVE = "delete_archive"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"


def _resolve_service_entry(
    hass: HomeAssistant,
    call: ServiceCall,
) -> QuitoqueConfigEntry:
    """Resolve the Quitoque config entry targeted by a service call."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]

    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(
                localize(
                    hass,
                    "Entrée de configuration Quitoque introuvable",
                    "Quitoque config entry not found",
                )
            )
        return entry

    if len(entries) == 1:
        return entries[0]

    if not entries:
        raise HomeAssistantError(
            localize(
                hass,
                "Aucune entrée Quitoque chargée",
                "No Quitoque config entry is loaded",
            )
        )

    raise HomeAssistantError(
        localize(
            hass,
            "Plusieurs comptes Quitoque sont configurés : précisez config_entry_id",
            "Multiple Quitoque accounts are configured: specify config_entry_id",
        )
    )


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register Quitoque domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    async def handle_refresh(call: ServiceCall):
        entry = _resolve_service_entry(hass, call)
        await async_refresh(entry)

    async def handle_sync_calendar(call: ServiceCall):
        entry = _resolve_service_entry(hass, call)
        created = await async_sync_calendar(entry)
        return {"created_events": created}

    async def handle_generate_pdfs(call: ServiceCall):
        entry = _resolve_service_entry(hass, call)
        result = await async_generate_pdfs(entry)
        return {
            "generated_count": len(result["generated"]),
            "errors": result["errors"],
            "archive_url": result["archive_url"],
        }

    async def handle_cleanup_pdfs(call: ServiceCall):
        entry = _resolve_service_entry(hass, call)
        return await async_cleanup_pdfs(entry)

    async def handle_delete_archive(call: ServiceCall):
        entry = _resolve_service_entry(hass, call)
        return await async_delete_recipes_archive(entry)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_CALENDAR,
        handle_sync_calendar,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_PDFS,
        handle_generate_pdfs,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_PDFS,
        handle_cleanup_pdfs,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ARCHIVE,
        handle_delete_archive,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_cleanup_pdfs(
    hass: HomeAssistant,
    entry: QuitoqueConfigEntry,
) -> None:
    """Delete expired generated Quitoque recipe PDFs."""
    retention_days = int(
        entry.options.get(
            CONF_PDF_RETENTION_DAYS,
            DEFAULT_PDF_RETENTION_DAYS,
        )
    )

    deleted, archive_deleted = await hass.async_add_executor_job(
        cleanup_expired_recipe_pdfs,
        hass.config.config_dir,
        retention_days,
    )

    if deleted or archive_deleted:
        _LOGGER.debug(
            "Nettoyage PDF Quitoque : deleted=%s archive_deleted=%s "
            "retention_days=%s",
            deleted,
            archive_deleted,
            retention_days,
        )


async def async_setup_entry(hass: HomeAssistant, entry: QuitoqueConfigEntry) -> bool:
    """Set up Quitoque from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=CookieJar())
    client = QuitoqueClient(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.options.get(
            CONF_RECIPES_URL,
            entry.data.get(CONF_RECIPES_URL),
        ),
    )
    coordinator = QuitoqueCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await session.close()
        raise
    entry.runtime_data = QuitoqueRuntimeData(coordinator, session)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await _async_cleanup_pdfs(hass, entry)

    async def _scheduled_pdf_cleanup(_now) -> None:
        await _async_cleanup_pdfs(hass, entry)

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _scheduled_pdf_cleanup,
            _PDF_CLEANUP_INTERVAL,
        )
    )

    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: QuitoqueConfigEntry
) -> None:
    """Reload Quitoque when its options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: QuitoqueConfigEntry) -> bool:
    """Unload Quitoque."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.session.close()
    return unloaded
