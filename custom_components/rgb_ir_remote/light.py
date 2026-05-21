"""Light entity for an RGB IR remote-controlled bulb.

The entity is driven by a :class:`RemoteProfile` looked up from the
config entry's ``remote_type`` field, so the same code path handles every
supported remote without conditional branches.
"""

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

from .codes import PROFILES, RemoteProfile, nearest_colour_effect
from .const import (
    BRIGHTNESS_STEPS,
    CONF_REMOTE_TYPE,
    CONF_TRANSMITTER,
    DOMAIN,
    REMOTE_TYPE_GENERIC_1,
)

_LOGGER = logging.getLogger(__name__)

INTER_PRESS_DELAY = 0.12  # seconds between consecutive IR frames
IR_SEND_TIMEOUT = 8.0  # seconds; bail out if the transmitter hangs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the bulb entity from a config entry."""
    remote_type: str = entry.data.get(CONF_REMOTE_TYPE, REMOTE_TYPE_GENERIC_1)
    profile = PROFILES.get(remote_type)
    if profile is None:
        raise HomeAssistantError(
            f"Unknown remote type {remote_type!r} on config entry {entry.entry_id}; "
            f"valid choices are {list(PROFILES)}"
        )
    async_add_entities(
        [
            RgbIrBulb(
                entry_id=entry.entry_id,
                name=entry.data[CONF_NAME],
                transmitter=entry.data[CONF_TRANSMITTER],
                profile=profile,
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
    """A bulb driven by NEC IR commands sourced from a RemoteProfile.

    No feedback channel exists, so state is assumed.
    """

    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self,
        *,
        entry_id: str,
        name: str,
        transmitter: str,
        profile: RemoteProfile,
    ) -> None:
        """Initialise the bulb."""
        self._profile = profile
        self._transmitter = transmitter
        self._attr_unique_id = entry_id
        self._attr_effect_list = profile.effect_list
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": name,
            "manufacturer": "Practical Series" if profile.id == "generic_1" else "Generic",
            "model": profile.label,
        }
        self._send_lock = asyncio.Lock()
        self._step = BRIGHTNESS_STEPS
        self._attr_brightness = _step_to_brightness(self._step)
        self._attr_is_on = False
        self._attr_effect = None
        # Default to the centre of the wheel (low-saturation point) so the
        # cursor starts somewhere sensible.
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
        if isinstance(effect, str) and effect in self._attr_effect_list:
            self._attr_effect = effect
        hs = last_state.attributes.get(ATTR_HS_COLOR)
        if (
            isinstance(hs, (list, tuple))
            and len(hs) == 2
            and all(isinstance(v, (int, float)) for v in hs)
        ):
            self._attr_hs_color = (float(hs[0]), float(hs[1]))

    async def _press_byte(self, byte: int) -> None:
        """Send one IR frame for a given command byte.

        Times out after ``IR_SEND_TIMEOUT`` so an unresponsive transmitter
        can't hold the lock indefinitely.
        """
        async with self._send_lock:
            try:
                async with asyncio.timeout(IR_SEND_TIMEOUT):
                    await async_send_command(
                        self.hass,
                        self._transmitter,
                        self._profile.command(byte),
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

    async def _press_repeated_byte(self, byte: int, count: int) -> None:
        """Press a byte N times, spaced to be reliably decoded."""
        for i in range(count):
            if i:
                await asyncio.sleep(INTER_PRESS_DELAY)
            await self._press_byte(byte)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bulb on, optionally setting colour, effect, or brightness."""
        was_on = self._attr_is_on
        sent_anything = False
        profile = self._profile

        if not was_on and profile.on_byte is not None:
            await self._press_byte(profile.on_byte)
            # Physical bulb wakes at full brightness on the row last selected.
            self._step = BRIGHTNESS_STEPS
            sent_anything = True

        # Colour wheel → snap to nearest preset
        if (hs := kwargs.get(ATTR_HS_COLOR)) is not None:
            hue, saturation = float(hs[0]), float(hs[1])
            effect = nearest_colour_effect(profile, hue, saturation)
            if effect is not None and (preset := profile.colours.get(effect)):
                if sent_anything:
                    await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press_byte(preset.byte)
                # Snap the reported colour so the wheel cursor reflects what
                # the bulb actually did.
                if preset.saturation < 1.0:
                    self._attr_hs_color = (0.0, 0.0)
                else:
                    self._attr_hs_color = (preset.hue, preset.saturation)
                self._attr_effect = None
                self._step = BRIGHTNESS_STEPS
                sent_anything = True

        # Effect (animation buttons; colours go through hs_color path above)
        if (effect_name := kwargs.get(ATTR_EFFECT)) is not None:
            byte = profile.effect_byte(effect_name)
            if byte is None:
                _LOGGER.warning("Unknown effect %s, ignoring", effect_name)
            else:
                if sent_anything:
                    await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press_byte(byte)
                self._attr_effect = effect_name
                self._step = BRIGHTNESS_STEPS
                sent_anything = True

        # Brightness — only if the profile has both ± buttons
        if (
            (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None
            and profile.has_brightness
        ):
            target = _brightness_to_step(brightness)
            delta = target - self._step
            if delta:
                byte = (
                    profile.bright_up_byte if delta > 0 else profile.bright_down_byte
                )
                assert byte is not None  # has_brightness guarantees this
                if sent_anything:
                    await asyncio.sleep(INTER_PRESS_DELAY)
                await self._press_repeated_byte(byte, abs(delta))
                self._step = target

        self._attr_is_on = True
        self._attr_brightness = _step_to_brightness(self._step)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bulb off."""
        if self._profile.off_byte is not None:
            await self._press_byte(self._profile.off_byte)
        self._attr_is_on = False
        self.async_write_ha_state()
