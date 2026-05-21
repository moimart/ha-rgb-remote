"""Code tables for the RGB IR Remote integration.

Two remote profiles ship today:

- ``generic_1`` — the Practical Series II 24-key remote. Standard NEC,
  8-bit address ``0x00``. All 21 button bytes captured + verified against
  the user's hardware on 2026-05-11.

- ``ledlamp`` — an LED-lamp remote with 24 buttons + a separate (RF)
  power button. Extended NEC with 16-bit address ``0xEF00``. The first
  12 button bytes are Flipper-Zero verified (sequential ``0x00`` …
  ``0x0B``); additional buttons can be added as the user scans them.

Adding a new profile = adding a new ``RemoteProfile(...)`` to ``PROFILES``.
``light.py`` doesn't need to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    # infrared-protocols >= 3.0 — split into commands/ subpackage
    from infrared_protocols.commands.nec import NECCommand
except ImportError:
    # infrared-protocols == 2.0.0 (shipped with HA 2026.4/2026.5) — flat module
    from infrared_protocols.commands import NECCommand  # type: ignore[no-redef]


@dataclass(frozen=True, slots=True)
class ColourPreset:
    """A single reachable colour: IR byte plus its HS coordinates.

    ``saturation`` 0 means a white preset and is special-cased by the
    nearest-colour search.
    """

    byte: int
    hue: float
    saturation: float = 100.0


@dataclass(frozen=True, slots=True)
class RemoteProfile:
    """All the data needed to drive one specific remote layout."""

    id: str                                  # stable storage key
    label: str                                # human-readable name in dropdowns
    address: int                              # NEC address (extended if > 0xFF)

    on_byte: int | None = None
    off_byte: int | None = None
    bright_up_byte: int | None = None
    bright_down_byte: int | None = None

    colours: dict[str, ColourPreset] = field(default_factory=dict)
    animations: dict[str, int] = field(default_factory=dict)

    def command(self, byte: int, repeat_count: int = 0) -> NECCommand:
        """Build the NEC command for one of this profile's byte values."""
        return NECCommand(
            address=self.address,
            command=byte,
            repeat_count=repeat_count,
        )

    @property
    def effect_list(self) -> list[str]:
        """The combined effect list shown to HA (colours + animations)."""
        return [*self.colours, *self.animations]

    def effect_byte(self, effect_name: str) -> int | None:
        """Return the byte for an effect name, whether colour or animation."""
        if (preset := self.colours.get(effect_name)) is not None:
            return preset.byte
        return self.animations.get(effect_name)

    @property
    def has_brightness(self) -> bool:
        """True if the remote has both brightness ± buttons."""
        return (
            self.bright_up_byte is not None
            and self.bright_down_byte is not None
        )


GENERIC_1 = RemoteProfile(
    id="generic_1",
    label="Generic 24-key RGB (Practical Series II)",
    address=0x00,
    on_byte=0x45,
    off_byte=0x47,
    bright_up_byte=0x15,
    bright_down_byte=0x09,
    colours={
        "Red":        ColourPreset(byte=0x16, hue=0,   saturation=100),
        "Orange":     ColourPreset(byte=0x0C, hue=15,  saturation=100),
        "Magenta":    ColourPreset(byte=0x08, hue=300, saturation=100),
        "Pink":       ColourPreset(byte=0x42, hue=340, saturation=70),
        "Green":      ColourPreset(byte=0x19, hue=120, saturation=100),
        "Lime":       ColourPreset(byte=0x18, hue=80,  saturation=95),
        "Amber":      ColourPreset(byte=0x1C, hue=40,  saturation=100),
        "Yellow":     ColourPreset(byte=0x52, hue=55,  saturation=100),
        "Blue":       ColourPreset(byte=0x0D, hue=240, saturation=100),
        "Sky Blue":   ColourPreset(byte=0x5E, hue=205, saturation=100),
        "Light Blue": ColourPreset(byte=0x5A, hue=185, saturation=85),
        "White":      ColourPreset(byte=0x4A, hue=0,   saturation=0),
    },
    animations={
        "Flash":  0x44,
        "Smooth": 0x07,
    },
)


LEDLAMP = RemoteProfile(
    id="ledlamp",
    label="LED Lamp (extended NEC 0xEF00)",
    # Extended NEC — high byte (0xEF) is independent of low byte (0x00).
    # NECCommand sees address > 0xFF and emits the high byte verbatim
    # rather than computing ~address.
    address=0xEF00,
    on_byte=0x03,
    off_byte=0x02,
    bright_up_byte=0x00,
    bright_down_byte=0x01,
    colours={
        "Red":     ColourPreset(byte=0x04, hue=0,   saturation=100),
        "Green":   ColourPreset(byte=0x05, hue=120, saturation=100),
        "Blue":    ColourPreset(byte=0x06, hue=240, saturation=100),
        "White":   ColourPreset(byte=0x07, hue=0,   saturation=0),
        # Row 3 — Flipper-verified bytes, HS values are eyeballed and may
        # need refinement after a real-bulb test.
        "Red 2":   ColourPreset(byte=0x08, hue=15,  saturation=100),
        "Green 2": ColourPreset(byte=0x09, hue=80,  saturation=95),
        "Blue 2":  ColourPreset(byte=0x0A, hue=200, saturation=100),
    },
    animations={
        "Flash": 0x0B,
    },
)


PROFILES: dict[str, RemoteProfile] = {
    GENERIC_1.id: GENERIC_1,
    LEDLAMP.id: LEDLAMP,
}


# === Nearest-colour matching, shared across all profiles ===

_WHITE_SATURATION_THRESHOLD = 15.0
_SATURATION_WEIGHT = 0.35


def _circular_hue_distance(a: float, b: float) -> float:
    """Shortest distance between two hue angles on the 0..360° circle."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def nearest_colour_effect(
    profile: RemoteProfile, hue: float, saturation: float
) -> str | None:
    """Return the effect name whose colour preset is closest to (hue, sat).

    Saturation below the threshold snaps to the white preset if the profile
    has one. Otherwise weighted circular hue + saturation distance picks
    the nearest saturated colour. Returns ``None`` if the profile defines
    no colour effects.
    """
    if not profile.colours:
        return None

    white_effect = next(
        (name for name, p in profile.colours.items() if p.saturation < 1.0),
        None,
    )
    if saturation < _WHITE_SATURATION_THRESHOLD and white_effect is not None:
        return white_effect

    saturated = {n: p for n, p in profile.colours.items() if p.saturation > 1.0}
    if not saturated:
        # Profile only has a white preset
        return next(iter(profile.colours))

    def distance(p: ColourPreset) -> float:
        hd = _circular_hue_distance(hue, p.hue)
        sd = abs(saturation - p.saturation)
        return hd + sd * _SATURATION_WEIGHT

    return min(saturated.items(), key=lambda kv: distance(kv[1]))[0]
