"""Notifications for newly editable Quitoque orders and selection deadlines."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import asyncio
import logging

from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOTIFY_BEFORE_DEADLINE,
    CONF_NOTIFY_CHANNEL,
    CONF_NOTIFY_DEADLINE_DAYS,
    CONF_NOTIFY_REMINDER_TIME,
    DEFAULT_NOTIFY_REMINDER_TIME,
    CONF_NOTIFY_MOBILE_TARGETS,
    CONF_NOTIFY_MOBILE_NEW_MESSAGE,
    CONF_NOTIFY_MOBILE_DEADLINE_MESSAGE,
    DEFAULT_NOTIFY_MOBILE_NEW_MESSAGE,
    DEFAULT_NOTIFY_MOBILE_DEADLINE_MESSAGE,
    CONF_NOTIFY_NEW_ORDER,
    DASHBOARD_URL,
    DEFAULT_NOTIFY_DEADLINE_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class QuitoqueOrderNotifications:
    """Track observed orders and sent alerts across Home Assistant restarts."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_order_notifications")
        self.loaded = False
        self.initialized = False
        self.seen: set[str] = set()
        self.reminded: set[str] = set()
        self._lock = asyncio.Lock()
        self._scheduled_reminders = []

    async def _load(self):
        if self.loaded:
            return
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.seen = {str(x) for x in saved.get("seen", [])}
            self.reminded = {str(x) for x in saved.get("reminded", [])}
            self.initialized = bool(saved.get("initialized", False))
        self.loaded = True

    def _option(self, key, default):
        return self.entry.options.get(key, self.entry.data.get(key, self.entry.options.get("notify_reminder_time", self.entry.data.get("notify_reminder_time", default)))) if key == CONF_NOTIFY_REMINDER_TIME else self.entry.options.get(key, self.entry.data.get(key, default))

    def _deadline(self, order):
        """Provisional observed rule: delivery minus six days at 23:59."""
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        return datetime.combine(
            order.delivery_date - timedelta(days=6), time(23, 59), tzinfo=zone
        )

    async def process(self, orders):
        """Evaluate successful polls; seed existing orders silently on first run."""
        async with self._lock:
            await self._process_locked(orders)
            self._schedule_reminders(orders)

    async def _process_locked(self, orders):
        await self._load()
        now = dt_util.now()
        first_poll = not self.initialized
        changed = first_poll
        days = max(1, min(7, int(self._option(
            CONF_NOTIFY_DEADLINE_DAYS, DEFAULT_NOTIFY_DEADLINE_DAYS
        ))))
        new_enabled = bool(self._option(CONF_NOTIFY_NEW_ORDER, False))
        deadline_enabled = bool(self._option(CONF_NOTIFY_BEFORE_DEADLINE, False))
        raw_time = str(self._option(CONF_NOTIFY_REMINDER_TIME, DEFAULT_NOTIFY_REMINDER_TIME))
        try:
            reminder_time = time.fromisoformat(raw_time)
        except ValueError:
            reminder_time = time(8, 0)
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        french = (self.hass.config.language or 'en').lower().startswith('fr')

        for order in orders:
            key = str(order.order_id)
            deadline = self._deadline(order)
            if key not in self.seen:
                self.seen.add(key)
                changed = True
                if not first_poll and new_enabled and now < deadline:
                    await self._notify(
                        f"new_{key}",
                        "Nouvelle sélection Quitoque disponible" if french else "New Quitoque recipe selection available",
                        (f"La box du {order.delivery_date:%d/%m/%Y} est modifiable. Pensez à choisir vos recettes." if french else f"Your box for {order.delivery_date:%d/%m/%Y} is now editable. Choose your recipes."),
                        order.recipes_url,
                        self._format_mobile(CONF_NOTIFY_MOBILE_NEW_MESSAGE, DEFAULT_NOTIFY_MOBILE_NEW_MESSAGE, order, deadline, french),
                    )

            # Only orders still editable may produce a deadline reminder.
            if now >= deadline or order.delivery_date < now.date():
                continue
            reminder_key = f"{key}:{days}"
            scheduled_at = datetime.combine(deadline.date() - timedelta(days=days), reminder_time, tzinfo=zone)
            if deadline_enabled and reminder_key not in self.reminded and now >= scheduled_at:
                # A first poll never sends alerts, including overdue reminders.
                self.reminded.add(reminder_key)
                changed = True
                if not first_poll:
                    await self._notify(
                        f"deadline_{key}_{days}",
                        "Quitoque : clôture des recettes" if french else "Quitoque: recipe selection deadline",
                        (f"La sélection de la box du {order.delivery_date:%d/%m/%Y} clôture le {deadline:%d/%m/%Y} à 23h59. Vérifiez vos recettes." if french else f"Recipe selection for your {order.delivery_date:%d/%m/%Y} box closes on {deadline:%d/%m/%Y} at 23:59. Check your recipes."),
                        order.recipes_url,
                        self._format_mobile(CONF_NOTIFY_MOBILE_DEADLINE_MESSAGE, DEFAULT_NOTIFY_MOBILE_DEADLINE_MESSAGE, order, deadline, french),
                    )

        if changed:
            self.initialized = True
            await self.store.async_save({
                "initialized": True,
                "seen": sorted(self.seen),
                "reminded": sorted(self.reminded),
            })

    def cancel_scheduled_reminders(self):
        """Cancel pending callbacks on reload or unload."""
        for cancel in self._scheduled_reminders:
            cancel()
        self._scheduled_reminders.clear()

    def _schedule_reminders(self, orders):
        """Schedule one-shot callbacks, without polling or additional API calls."""
        self.cancel_scheduled_reminders()
        if not self._option(CONF_NOTIFY_BEFORE_DEADLINE, False):
            return

        now = dt_util.now()
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        days = max(1, min(7, int(self._option(
            CONF_NOTIFY_DEADLINE_DAYS, DEFAULT_NOTIFY_DEADLINE_DAYS
        ))))
        try:
            reminder_time = time.fromisoformat(str(
                self._option(CONF_NOTIFY_REMINDER_TIME, DEFAULT_NOTIFY_REMINDER_TIME)
            ))
        except ValueError:
            reminder_time = time(8, 0)

        for order in orders:
            deadline = self._deadline(order)
            reminder_key = f"{order.order_id}:{days}"
            if reminder_key in self.reminded or now >= deadline:
                continue
            scheduled_at = datetime.combine(
                deadline.date() - timedelta(days=days), reminder_time, tzinfo=zone
            )
            if scheduled_at <= now:
                # Overdue reminders are handled by process() on startup/refresh.
                continue

            async def _send_reminder(_now, current_orders=orders):
                await self.process(current_orders)

            self._scheduled_reminders.append(
                async_track_point_in_time(self.hass, _send_reminder, scheduled_at)
            )

    def _format_mobile(self, option, default, order, deadline, french):
        """Replace only documented tokens, preserving other text literally."""
        template = self._option(option, default)
        english_default = ("Your box for {delivery_date} is now editable. Choose your recipes!" if option == CONF_NOTIFY_MOBILE_NEW_MESSAGE else "Your box for {delivery_date} closes on {deadline_date} at 23:59. Check your recipes!")
        if not french and template == default:
            template = english_default
        if not isinstance(template, str) or not template.strip():
            template = default if french else english_default
        values = {
            "{delivery_date}": order.delivery_date.strftime("%d/%m/%Y"),
            "{deadline_date}": deadline.strftime("%d/%m/%Y"),
            "{order_id}": str(order.order_id),
        }
        for token, value in values.items():
            template = template.replace(token, value)
        return template

    async def _notify(self, suffix, title, message, url, mobile_message=None):
        if not isinstance(url, str) or not url.startswith("https://www.quitoque.fr/"):
            url = DASHBOARD_URL
        channel = self._option(CONF_NOTIFY_CHANNEL, "persistent")
        link_label = "Modifier ma box" if (self.hass.config.language or "en").lower().startswith("fr") else "Edit my box"
        if channel in ("persistent", "both"):
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": f"{message}\n\n[{link_label}]({url})",
                        "notification_id": f"quitoque_{self.entry.entry_id}_{suffix}",
                    },
                    blocking=True,
                )
            except Exception:
                _LOGGER.exception("Impossible de créer la notification persistante Quitoque")

        if channel in ("mobile", "both"):
            targets = self._option(CONF_NOTIFY_MOBILE_TARGETS, [])
            for target in targets if isinstance(targets, list) else []:
                if not isinstance(target, str) or not target.startswith("mobile_app_"):
                    continue
                if not self.hass.services.has_service("notify", target):
                    _LOGGER.warning("Service de notification mobile indisponible : %s", target)
                    continue
                try:
                    await self.hass.services.async_call(
                        "notify",
                        target,
                        {
                            "title": title,
                            "message": mobile_message or message,
                            "data": {"url": url, "clickAction": url},
                        },
                        blocking=True,
                    )
                except Exception:
                    _LOGGER.exception("Échec de notification mobile Quitoque : %s", target)
