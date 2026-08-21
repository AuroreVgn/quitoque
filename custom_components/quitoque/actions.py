"""User-triggered Quitoque actions shared by buttons and services."""

from __future__ import annotations

from datetime import date, timedelta
import time
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.components import persistent_notification
from homeassistant.util import dt as dt_util

from .calendar_import import async_import_orders
from .i18n import localize
from .const import (
    CONF_EVENT_PREFIX,
    CONF_NOTIFY_AFTER_SYNC,
    CONF_TARGET_CALENDAR,
    DEFAULT_NOTIFY_AFTER_SYNC,
)
from .pdf_export import (
    PDF_ARCHIVE_LOCAL_URL,
    clear_generated_recipe_files,
    delete_recipes_archive,
    generate_recipe_pdf,
    generate_recipes_archive,
    prepare_pdf_directory,
    recipe_pdf_filename,
    recipe_pdf_local_url,
)

if TYPE_CHECKING:
    from . import QuitoqueConfigEntry

STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_NO_DELIVERY = "no_delivery"


def managed_orders(entry: QuitoqueConfigEntry):
    """Return only the orders belonging to S+2, S+3 and S+4."""
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    start = current_monday + timedelta(weeks=2)
    end = current_monday + timedelta(weeks=5)

    return tuple(
        order
        for order in entry.runtime_data.coordinator.orders
        if start <= order.delivery_date < end
    )


def _sensor(entry: QuitoqueConfigEntry, action_key: str):
    return entry.runtime_data.coordinator.hass.data.get(
        "quitoque_action_sensors", {}
    ).get((entry.entry_id, action_key))


def _set_sensor(entry: QuitoqueConfigEntry, action_key: str, value) -> None:
    sensor = _sensor(entry, action_key)
    if sensor is not None:
        sensor.set_value(value)


def _set_status(
    entry: QuitoqueConfigEntry,
    status: str,
    error: str | None = None,
) -> None:
    _set_sensor(entry, "last_status", status)
    _set_sensor(entry, "last_error", error or "none")


def _set_busy(entry: QuitoqueConfigEntry, value: bool) -> None:
    coordinator = entry.runtime_data.coordinator
    coordinator.operation_in_progress = value
    coordinator.async_update_listeners()


def _ensure_not_busy(entry: QuitoqueConfigEntry) -> None:
    if entry.runtime_data.coordinator.operation_in_progress:
        raise HomeAssistantError(
            localize(
                entry.runtime_data.coordinator.hass,
                "Une opération Quitoque est déjà en cours",
                "A Quitoque operation is already in progress",
            )
        )


async def async_refresh(entry: QuitoqueConfigEntry) -> None:
    """Refresh Quitoque data."""
    _ensure_not_busy(entry)
    _set_busy(entry, True)
    try:
        await entry.runtime_data.coordinator.async_request_refresh()
        _set_status(entry, STATUS_SUCCESS)
    except Exception as err:
        _set_status(entry, STATUS_ERROR, str(err))
        raise
    finally:
        _set_busy(entry, False)


async def async_sync_calendar(entry: QuitoqueConfigEntry) -> int:
    """Refresh and import S+2/S+3/S+4 into the target calendar."""
    _ensure_not_busy(entry)
    _set_busy(entry, True)
    try:
        coordinator = entry.runtime_data.coordinator
        await coordinator.async_request_refresh()

        orders = managed_orders(entry)
        if not orders:
            _set_status(entry, STATUS_NO_DELIVERY)
            return 0

        created = await async_import_orders(
            coordinator.hass,
            entry.options.get(
                CONF_TARGET_CALENDAR,
                entry.data[CONF_TARGET_CALENDAR],
            ),
            orders,
            entry.options.get(
                CONF_EVENT_PREFIX,
                entry.data.get(CONF_EVENT_PREFIX, ""),
            ),
        )

        _set_sensor(entry, "last_calendar_sync", dt_util.utcnow())
        _set_status(entry, STATUS_SUCCESS)

        if entry.options.get(
            CONF_NOTIFY_AFTER_SYNC,
            entry.data.get(CONF_NOTIFY_AFTER_SYNC, DEFAULT_NOTIFY_AFTER_SYNC),
        ):
            if localize(coordinator.hass, "fr", "en") == "fr":
                notification_title = "Synchronisation Quitoque"
                notification_message = (
                    f"Synchronisation Quitoque terminée : {created} "
                    f"événement(s) créé(s) dans le calendrier."
                )
            else:
                notification_title = "Quitoque synchronization"
                notification_message = (
                    f"Quitoque synchronization complete: {created} "
                    f"event(s) created in the calendar."
                )

            persistent_notification.async_create(
                coordinator.hass,
                notification_message,
                title=notification_title,
                notification_id=f"quitoque_sync_{entry.entry_id}",
            )

        return created
    except Exception as err:
        _set_status(entry, STATUS_ERROR, str(err))
        raise
    finally:
        _set_busy(entry, False)


async def async_generate_pdfs(entry: QuitoqueConfigEntry) -> dict:
    """Generate PDFs and the ZIP archive for S+2/S+3/S+4."""
    _ensure_not_busy(entry)
    _set_busy(entry, True)

    coordinator = entry.runtime_data.coordinator
    hass = coordinator.hass

    try:
        await coordinator.async_request_refresh()
        orders = managed_orders(entry)

        if not orders:
            _set_status(entry, STATUS_NO_DELIVERY)
            return {
                "generated": [],
                "errors": [],
                "archive_url": None,
            }

        output_directory = await hass.async_add_executor_job(
            prepare_pdf_directory,
            hass.config.config_dir,
        )

        generated: list[tuple[str, str]] = []
        errors: list[str] = []

        for order in orders:
            for recipe in order.recipes:
                try:
                    details = await coordinator.client.async_get_recipe_details(
                        recipe
                    )
                    image_bytes = None
                    if details.image_url:
                        try:
                            image_bytes = await coordinator.client.async_get_image_bytes(
                                details.image_url
                            )
                        except Exception:
                            image_bytes = None

                    filename = recipe_pdf_filename(recipe.name)
                    output_path = output_directory / filename
                    await hass.async_add_executor_job(
                        generate_recipe_pdf,
                        str(output_path),
                        details,
                        image_bytes,
                    )
                    generated.append(
                        (recipe.name, recipe_pdf_local_url(recipe.name))
                    )
                except Exception as err:
                    errors.append(f"{recipe.name}: {err}")

        archive_url = None
        if generated:
            await hass.async_add_executor_job(
                generate_recipes_archive,
                hass.config.config_dir,
                str(output_directory),
            )
            _set_sensor(entry, "last_pdf_generation", dt_util.utcnow())
            archive_url = f"{PDF_ARCHIVE_LOCAL_URL}?v={time.time_ns()}"

        if errors and not generated:
            _set_status(entry, STATUS_ERROR, "; ".join(errors))
        elif errors:
            _set_status(entry, STATUS_SUCCESS, "; ".join(errors))
        else:
            _set_status(entry, STATUS_SUCCESS)

        return {
            "generated": generated,
            "errors": errors,
            "archive_url": archive_url,
        }
    except Exception as err:
        _set_status(entry, STATUS_ERROR, str(err))
        raise
    finally:
        _set_busy(entry, False)



async def async_cleanup_pdfs(entry: QuitoqueConfigEntry) -> dict:
    """Immediately delete generated Quitoque PDFs and ZIP archive."""
    _ensure_not_busy(entry)
    _set_busy(entry, True)
    try:
        deleted, archive_deleted = await entry.runtime_data.coordinator.hass.async_add_executor_job(
            clear_generated_recipe_files,
            entry.runtime_data.coordinator.hass.config.config_dir,
        )
        _set_status(entry, STATUS_SUCCESS)
        return {
            "deleted_pdfs": deleted,
            "archive_deleted": archive_deleted,
        }
    except Exception as err:
        _set_status(entry, STATUS_ERROR, str(err))
        raise
    finally:
        _set_busy(entry, False)



async def async_delete_recipes_archive(entry: QuitoqueConfigEntry) -> dict:
    """Delete only the generated ZIP archive, keeping individual PDFs."""
    _ensure_not_busy(entry)
    _set_busy(entry, True)

    hass = entry.runtime_data.coordinator.hass
    try:
        archive_deleted = await hass.async_add_executor_job(
            delete_recipes_archive,
            hass.config.config_dir,
        )
        _set_status(entry, STATUS_SUCCESS)
        return {"archive_deleted": archive_deleted}
    except Exception as err:
        _set_status(entry, STATUS_ERROR, str(err))
        raise
    finally:
        _set_busy(entry, False)
