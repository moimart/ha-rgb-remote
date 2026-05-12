"""Light entity for an RGB IR remote-controlled bulb."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.infrared import async_send_command
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .codes import (
    COLOUR_PRESETS_HS,
    EFFECT_LIST,
    EFFECT_TO_BUTTON,
    BulbCommand,
    nearest_colour_preset,
)
from .const import BRIGHTNESS_STEPS, CONF_TRANSMITTER, DOMAIN

_LOGGER = logging.getLogger(__name__)

INTER_PRESS_DELAY = 0.12  # seconds between consecutive IR frames
IR_SEND_TIMEOUT = 8.0  # seconds; bail out if the transmitter hangs


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
    """A bulb driven by NEC IR commands.

    Colour: continuous HS picker that snaps to the nearest of 12 reachable
    presets and sends that IR code; `hs_color` is updated to the snapped
    value so the wheel cursor honestly reflects what the bulb did.

    Brightness: dead-reckoned in BRIGHTNESS_STEPS buckets — every BR+ / BR-
    press shifts one bucket. Pressing a colour or power-on resets the bucket
    to max, matching how the physical bulb behaves.

    No feedback channel exists, so state is assumed.
    """

    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST

    def __init__(self, *, entry_id: str, name: str, transmitter: str) -> None:
        """Initialise the bulb."""
        self._transmitter = transmitter
        self._attr_unique_id = entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": name,
            "manufacturer": "Practical Series",
            "model": "II GU10 RGB IR Bulb",
        }
        self._send_lock = asyncio.Lock()
        self._step = BRIGHTNESS_STEPS
        self._attr_brightness = _step_to_brightness(self._step)
        self._attr_is_on = False
        self._attr_effect = None
        # Default to White on first start so the wheel cursor has a sensible
        # initial position (saturation=0 → centre of the wheel).
        self._attr_hs_color = (0.0, 0.0)

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
        hs = last_state.attributes.get(ATTR_HS_COLOR)
        if (
            isinstance(hs, (list, tuple))
            and len(hs) == 2
            and all(isinstance(v, (int, float)) for v in hs)
        ):
            self._attr_hs_color = (float(hs[0]), float(hs[1]))

    async def _press(self, button: BulbCommand) -> None:
        """Send one IR frame for a single button press.

        Times out after ``IR_SEND_TIMEOUT`` so an unresponsive transmitter
        can't hold the lock indefinitely and freeze every subsequent press.
        """
        async with self._send_lock:
            try:
                async with asyncio.timeout(IR_SEND_TIMEOUT):
                    await async_send_command(
                        self.hass, self._transmitter, button.to_command()
                    )
            except TimeoutError as err:
                _LOGGER.warning(
                    "IR send via %s timed out after %ss",
                    self._transmitter,
                    IR_SEND_TIMEOUT,
                )
                raise HomeAssistantError(
                    f"IR transmitter {self._transmitter} did not respond "
                    f"within {IR_SEND_TIMEOUT}s"
                ) from err

    async def _press_repeated(self, button: BulbCommand, count: int) -> None:
        """Press a button N times, spaced to be reliably decoded."""
        for i in range(count):
            if i:
                await asyncio.sleep(INTER_PRESS_DELAY)
            await self._press(button)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bulb on, optionally setting colour, effect, or brightness."""
        was_on = self._attr_is_on
        sent_anything = False

        if not was_on:
            await self._press(BulbCommand.ON)
            # Physical bulb wakes at full brightness on the row last selected.
            self._step = BRIGHTNESS_STEPS
            sent_anything = True

        # Colour wheel input — snap to nearest reachable preset.
        if (hs := kwargs.get(ATTR_HS_COLOR)) is not None:
            hue, saturation = float(hs[0]), float(hs[1])
            button = nearest_colour_preset(hue, saturation)
            if sent_anything:
                await asyncio.sleep(INTER_PRESS_DELAY)
            await self._press(button)
            # Snap the reported colour to the preset we actually sent, so the
            # wheel cursor honestly reflects what the bulb did.
            if button == BulbCommand.WHITE:
                self._attr_hs_color = (0.0, 0.0)
            else:
                self._attr_hs_color = COLOUR_PRESETS_HS[button]
            # Selecting a colour cancels any active animation.
            self._attr_effect = None
            self._step = BRIGHTNESS_STEPS
            sent_anything = True

        # Effect — only Flash / Smooth here; named colours go through hs_color.
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            button = EFFECT_TO_BUTTON.get(effect)
            if button is None:
                _LOGGER.warning("Unknown effect %s, ignoring", effect)
            else:
                if sent_anything:
                    await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press(button)
                self._attr_effect = effect
                self._step = BRIGHTNESS_STEPS
                sent_anything = True

        # Brightness — dead-reckoned BR+/BR- presses.
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            target = _brightness_to_step(brightness)
            delta = target - self._step
            if delta:
                button = (
                    BulbCommand.BRIGHTNESS_UP if delta > 0 else BulbCommand.BRIGHTNESS_DOWN
                )
                if sent_anything:
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
