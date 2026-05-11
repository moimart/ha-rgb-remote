"""Light entity for an RGB IR remote-controlled bulb."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.infrared import async_send_command
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .codes import EFFECT_LIST, EFFECT_TO_BUTTON, BulbCommand
from .const import BRIGHTNESS_STEPS, CONF_TRANSMITTER, DOMAIN

_LOGGER = logging.getLogger(__name__)

INTER_PRESS_DELAY = 0.12  # seconds between consecutive IR frames


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the bulb entity from a config entry."""
    async_add_entities(
        [
            RgbIrBulb(
                entry_id=entry.entry_id,
                name=entry.data[CONF_NAME],
                transmitter=entry.data[CONF_TRANSMITTER],
            )
        ]
    )


def _brightness_to_step(brightness: int) -> int:
    """Map HA brightness (0..255) to a 1..BRIGHTNESS_STEPS bucket."""
    if brightness <= 0:
        return 1
    step = round(brightness / 255 * BRIGHTNESS_STEPS)
    return max(1, min(BRIGHTNESS_STEPS, step))


def _step_to_brightness(step: int) -> int:
    """Map a 1..BRIGHTNESS_STEPS bucket back to HA brightness 0..255."""
    return round(step / BRIGHTNESS_STEPS * 255)


class RgbIrBulb(LightEntity, RestoreEntity):
    """A bulb driven by 24-key NEC IR commands.

    No feedback channel exists, so state is assumed. Brightness is dead-
    reckoned in BRIGHTNESS_STEPS buckets — every BR+ / BR- press shifts
    one bucket. Pressing a color or power-on resets the bucket to max,
    matching how the physical bulb behaves.
    """

    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST

    def __init__(self, *, entry_id: str, name: str, transmitter: str) -> None:
        """Initialise the bulb."""
        self._transmitter = transmitter
        self._attr_unique_id = entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": name,
            "manufacturer": "Generic",
            "model": "24-key RGB IR Bulb",
        }
        self._send_lock = asyncio.Lock()
        self._step = BRIGHTNESS_STEPS
        self._attr_brightness = _step_to_brightness(self._step)
        self._attr_is_on = False
        self._attr_effect = None

    async def async_added_to_hass(self) -> None:
        """Restore last state across restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        self._attr_is_on = last_state.state == "on"
        brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
        if isinstance(brightness, int):
            self._attr_brightness = brightness
            self._step = _brightness_to_step(brightness)
        effect = last_state.attributes.get(ATTR_EFFECT)
        if isinstance(effect, str) and effect in EFFECT_TO_BUTTON:
            self._attr_effect = effect

    async def _press(self, button: BulbCommand) -> None:
        """Send one IR frame for a single button press."""
        async with self._send_lock:
            await async_send_command(
                self.hass, self._transmitter, button.to_command()
            )

    async def _press_repeated(self, button: BulbCommand, count: int) -> None:
        """Press a button N times, spaced to be reliably decoded."""
        for i in range(count):
            if i:
                await asyncio.sleep(INTER_PRESS_DELAY)
            await self._press(button)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bulb on, optionally setting effect and/or brightness."""
        was_on = self._attr_is_on

        if not was_on:
            await self._press(BulbCommand.ON)
            # Physical bulb wakes at full brightness on the row last selected.
            self._step = BRIGHTNESS_STEPS

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            button = EFFECT_TO_BUTTON.get(effect)
            if button is None:
                _LOGGER.warning("Unknown effect %s, ignoring", effect)
            else:
                if was_on:
                    # Settle after the previous frame so the bulb sees a fresh code.
                    await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press(button)
                self._attr_effect = effect
                # Selecting a colour/mode resets brightness to max on these bulbs.
                self._step = BRIGHTNESS_STEPS

        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            target = _brightness_to_step(brightness)
            delta = target - self._step
            if delta:
                button = (
                    BulbCommand.BRIGHTNESS_UP if delta > 0 else BulbCommand.BRIGHTNESS_DOWN
                )
                await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press_repeated(button, abs(delta))
                self._step = target

        self._attr_is_on = True
        self._attr_brightness = _step_to_brightness(self._step)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bulb off."""
        await self._press(BulbCommand.OFF)
        self._attr_is_on = False
        self.async_write_ha_state()
