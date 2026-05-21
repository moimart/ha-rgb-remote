"""Config flow for the RGB IR Remote Bulb integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import async_get_emitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .codes import PROFILES
from .definitions import (
    CONF_REMOTE_TYPE,
    CONF_TRANSMITTER,
    DOMAIN,
    REMOTE_TYPE_GENERIC_1,
)


class RgbIrRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a name, a remote type, and an IR transmitter."""

    # Bump when entry.data schema changes — see async_migrate_entry.
    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial step: name + remote type + transmitter."""
        emitters = async_get_emitters(self.hass)
        if not emitters:
            return self.async_abort(reason="no_emitters")

        errors: dict[str, str] = {}

        if user_input is not None:
            transmitter: str = user_input[CONF_TRANSMITTER]
            name: str = user_input[CONF_NAME].strip()
            remote_type: str = user_input[CONF_REMOTE_TYPE]
            if not name:
                errors[CONF_NAME] = "name_required"
            elif transmitter not in emitters:
                errors[CONF_TRANSMITTER] = "transmitter_unavailable"
            elif remote_type not in PROFILES:
                errors[CONF_REMOTE_TYPE] = "remote_type_invalid"
            else:
                await self.async_set_unique_id(f"{transmitter}::{name.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_TRANSMITTER: transmitter,
                        CONF_NAME: name,
                        CONF_REMOTE_TYPE: remote_type,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(
                    CONF_REMOTE_TYPE, default=REMOTE_TYPE_GENERIC_1
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=profile.id, label=profile.label)
                            for profile in PROFILES.values()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_TRANSMITTER): EntitySelector(
                    EntitySelectorConfig(include_entities=list(emitters))
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
