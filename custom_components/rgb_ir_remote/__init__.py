"""RGB IR Remote Bulb integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .definitions import CONF_REMOTE_TYPE, REMOTE_TYPE_GENERIC_1

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a bulb from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config-entry data to the current schema version.

    Pre-v2 entries didn't store ``remote_type``. Default them to the
    Practical Series II profile so they keep behaving exactly as before.
    """
    if entry.version == 1:
        new_data = {**entry.data, CONF_REMOTE_TYPE: REMOTE_TYPE_GENERIC_1}
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrated %s to v2: defaulted remote_type to %s",
            entry.entry_id,
            REMOTE_TYPE_GENERIC_1,
        )
    return True
