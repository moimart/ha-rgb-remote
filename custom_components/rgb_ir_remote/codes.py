"""NEC code table for the Practical Series II GU10 RGB bulb.

All 21 buttons captured + decoded with valid NEC inverse-byte checksums
against the user's actual hardware on 2026-05-11. The bulb uses standard
NEC at 38 kHz with address 0x00.

Remote layout (Practical Series II — 7 rows × 3 columns):

    Row 1:  On         Dim          Off
    Row 2:  C (Flash)  Timer 24H    Timer 1H
    Row 3:  S (Smooth) Brightness+  Brightness-
    Row 4:  Red        Green        Blue
    Row 5:  Orange     Lime         Sky Blue
    Row 6:  Magenta    Amber        Light Blue
    Row 7:  Pink       Yellow       White
"""

from __future__ import annotations

from enum import IntEnum

try:
    # infrared-protocols >= 3.0 — split into commands/ subpackage
    from infrared_protocols.commands.nec import NECCommand
except ImportError:
    # infrared-protocols == 2.0.0 (shipped with HA 2026.4/2026.5) — flat module
    from infrared_protocols.commands import NECCommand  # type: ignore[no-redef]

ADDRESS = 0x00


class BulbCommand(IntEnum):
    """All 21 buttons of the Practical Series II RGB remote."""

    # Row 1 — power + dim
    ON = 0x45
    DIM = 0x46
    OFF = 0x47

    # Row 2 — colour cycling + timers
    FLASH = 0x44       # "C" — drastic colour cycling
    TIMER_24H = 0x40
    TIMER_1H = 0x43

    # Row 3 — smooth cycling + brightness
    SMOOTH = 0x07      # "S" — smooth colour cycling
    BRIGHTNESS_UP = 0x15
    BRIGHTNESS_DOWN = 0x09

    # Row 4 — main labelled colours
    RED_1 = 0x16
    GREEN_1 = 0x19
    BLUE_1 = 0x0D

    # Row 5
    RED_2 = 0x0C       # orange
    GREEN_2 = 0x18     # lime
    BLUE_2 = 0x5E      # sky blue

    # Row 6
    RED_3 = 0x08       # magenta
    GREEN_3 = 0x1C     # amber
    BLUE_3 = 0x5A      # light blue

    # Row 7
    RED_4 = 0x42       # pink
    GREEN_4 = 0x52     # yellow
    WHITE = 0x4A

    def to_command(self, repeat_count: int = 0) -> NECCommand:
        """Build the NECCommand for this button press."""
        return NECCommand(
            address=ADDRESS,
            command=self.value,
            repeat_count=repeat_count,
        )


# Approximate (hue, saturation) values for each of the 12 reachable colours,
# eyeballed from the remote photo. Used to snap the HA colour-wheel input
# to the nearest available preset. Saturation is on the HA scale (0..100).
COLOUR_PRESETS_HS: dict[BulbCommand, tuple[float, float]] = {
    BulbCommand.RED_1:   (0,    100),  # pure red
    BulbCommand.RED_2:   (15,   100),  # orange-red
    BulbCommand.GREEN_3: (40,   100),  # amber
    BulbCommand.GREEN_4: (55,   100),  # yellow
    BulbCommand.GREEN_2: (80,    95),  # lime
    BulbCommand.GREEN_1: (120,  100),  # green
    BulbCommand.BLUE_3:  (185,   85),  # light blue (cyan-ish)
    BulbCommand.BLUE_2:  (205,  100),  # sky blue
    BulbCommand.BLUE_1:  (240,  100),  # pure blue
    BulbCommand.RED_3:   (300,  100),  # magenta
    BulbCommand.RED_4:   (340,   70),  # pink (lighter)
}

# Saturation below this threshold snaps to White regardless of hue.
_WHITE_SATURATION_THRESHOLD = 15.0

# Hue weighting vs saturation in the distance metric. Hue dominates because
# the human eye is more sensitive to hue shifts than to saturation shifts.
_SATURATION_WEIGHT = 0.35


def _circular_hue_distance(a: float, b: float) -> float:
    """Shortest distance between two hue angles on the 0..360° circle."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def nearest_colour_preset(hue: float, saturation: float) -> BulbCommand:
    """Return the BulbCommand whose colour preset is closest to (hue, saturation).

    Low-saturation requests snap to WHITE; otherwise we minimise a weighted
    circular hue + saturation distance over the 11 saturated presets.
    """
    if saturation < _WHITE_SATURATION_THRESHOLD:
        return BulbCommand.WHITE

    def distance(preset: tuple[float, float]) -> float:
        hd = _circular_hue_distance(hue, preset[0])
        sd = abs(saturation - preset[1])
        return hd + sd * _SATURATION_WEIGHT

    return min(COLOUR_PRESETS_HS.items(), key=lambda kv: distance(kv[1]))[0]


# Only cycling animations remain as named effects now that named colours
# are reachable via the HS colour wheel.
EFFECT_TO_BUTTON: dict[str, BulbCommand] = {
    "Flash": BulbCommand.FLASH,
    "Smooth": BulbCommand.SMOOTH,
}

EFFECT_LIST: list[str] = list(EFFECT_TO_BUTTON.keys())
