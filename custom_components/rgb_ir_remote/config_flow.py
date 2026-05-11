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
)

from .const import CONF_TRANSMITTER, DOMAIN


class RgbIrRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Walk the user through naming a bulb and picking an IR emitter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial step: pick a transmitter and name the bulb."""
        emitters = async_get_emitters(self.hass)
        if not emitters:
            return self.async_abort(reason="no_emitters")

        errors: dict[str, str] = {}

        if user_input is not None:
            transmitter: str = user_input[CONF_TRANSMITTER]
            name: str = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif transmitter not in emitters:
                errors[CONF_TRANSMITTER] = "transmitter_unavailable"
            else:
                await self.async_set_unique_id(f"{transmitter}::{name.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_TRANSMITTER: transmitter,
                        CONF_NAME: name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_TRANSMITTER): EntitySelector(
                    EntitySelectorConfig(
                        include_entities=list(emitters),
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
