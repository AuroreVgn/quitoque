"""Config flow for Quitoque."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, CookieJar
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import QuitoqueAuthenticationError, QuitoqueClient, QuitoqueError
from .const import (
    CONF_EVENT_PREFIX,
    CONF_PDF_RETENTION_DAYS,
    CONF_NOTIFY_AFTER_SYNC,
    CONF_RECIPES_URL,
    CONF_TARGET_CALENDAR,
    DEFAULT_NAME,
    DEFAULT_PDF_RETENTION_DAYS,
    DEFAULT_NOTIFY_AFTER_SYNC,
    DOMAIN,
)


async def _async_validate_login(
    username: str, password: str, recipes_url: str | None
):
    """Validate credentials with an isolated cookie jar."""
    async with ClientSession(cookie_jar=CookieJar()) as session:
        client = QuitoqueClient(session, username, password, recipes_url)
        return await client.async_get_order()


class QuitoqueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Quitoque config flow."""

    VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            recipes_url = user_input.get(CONF_RECIPES_URL, "").strip()
            try:
                order = await _async_validate_login(
                    username, password, recipes_url or None
                )
            except QuitoqueAuthenticationError:
                errors["base"] = "invalid_auth"
            except QuitoqueError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_RECIPES_URL: recipes_url,
                        CONF_TARGET_CALENDAR: user_input[CONF_TARGET_CALENDAR],
                        CONF_EVENT_PREFIX: user_input.get(CONF_EVENT_PREFIX, "").strip(),
                        CONF_PDF_RETENTION_DAYS: user_input.get(
                            CONF_PDF_RETENTION_DAYS, DEFAULT_PDF_RETENTION_DAYS
                        ),
                        CONF_NOTIFY_AFTER_SYNC: bool(
                            user_input.get(
                                CONF_NOTIFY_AFTER_SYNC,
                                DEFAULT_NOTIFY_AFTER_SYNC,
                            )
                        ),
                    },
                    options={},
                    description_placeholders={"delivery": order.delivery_date.isoformat() if order is not None else "Non"},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_RECIPES_URL, default=""): str,
                vol.Optional(CONF_EVENT_PREFIX, default=""): str,
                vol.Optional(
                    CONF_PDF_RETENTION_DAYS, default=DEFAULT_PDF_RETENTION_DAYS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=365,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="jours",
                    )
                ),
                vol.Optional(
                    CONF_NOTIFY_AFTER_SYNC,
                    default=DEFAULT_NOTIFY_AFTER_SYNC,
                ): selector.BooleanSelector(),
                vol.Required(CONF_TARGET_CALENDAR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="calendar")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Start reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await _async_validate_login(
                    username,
                    password,
                    self._reauth_entry.data.get(CONF_RECIPES_URL) or None,
                )
            except QuitoqueAuthenticationError:
                errors["base"] = "invalid_auth"
            except QuitoqueError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        defaults = self._reauth_entry.data if self._reauth_entry else {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return QuitoqueOptionsFlow(config_entry)


class QuitoqueOptionsFlow(config_entries.OptionsFlow):
    """Handle Quitoque options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_RECIPES_URL: user_input.get(CONF_RECIPES_URL, "").strip(),
                    CONF_TARGET_CALENDAR: user_input[CONF_TARGET_CALENDAR],
                    CONF_EVENT_PREFIX: user_input.get(CONF_EVENT_PREFIX, "").strip(),
                    CONF_PDF_RETENTION_DAYS: int(
                        user_input.get(CONF_PDF_RETENTION_DAYS, DEFAULT_PDF_RETENTION_DAYS)
                    ),
                    CONF_NOTIFY_AFTER_SYNC: bool(
                        user_input.get(CONF_NOTIFY_AFTER_SYNC, DEFAULT_NOTIFY_AFTER_SYNC)
                    ),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RECIPES_URL,
                        default=self._entry.options.get(
                            CONF_RECIPES_URL, self._entry.data.get(CONF_RECIPES_URL, "")
                        ),
                    ): str,
                    vol.Optional(
                        CONF_EVENT_PREFIX,
                        default=self._entry.options.get(
                            CONF_EVENT_PREFIX, self._entry.data.get(CONF_EVENT_PREFIX, "")
                        ),
                    ): str,
                    vol.Optional(
                        CONF_PDF_RETENTION_DAYS,
                        default=self._entry.options.get(
                            CONF_PDF_RETENTION_DAYS,
                            self._entry.data.get(CONF_PDF_RETENTION_DAYS, DEFAULT_PDF_RETENTION_DAYS),
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=365, step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="jours",
                        )
                    ),
                    vol.Optional(
                        CONF_NOTIFY_AFTER_SYNC,
                        default=self._entry.options.get(
                            CONF_NOTIFY_AFTER_SYNC,
                            self._entry.data.get(CONF_NOTIFY_AFTER_SYNC, DEFAULT_NOTIFY_AFTER_SYNC),
                        ),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_TARGET_CALENDAR,
                        default=self._entry.options.get(
                            CONF_TARGET_CALENDAR, self._entry.data[CONF_TARGET_CALENDAR]
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="calendar")
                    ),
                }
            ),
        )
