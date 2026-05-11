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


# 12 colour effects (4 reds, 4 greens, 3 blues, white) + 2 cycling animations.
# Dim, Timer 24H, Timer 1H are not light effects — they'll be exposed as
# separate button.* entities in a follow-up release.
EFFECT_TO_BUTTON: dict[str, BulbCommand] = {
    "Red": BulbCommand.RED_1,
    "Orange": BulbCommand.RED_2,
    "Magenta": BulbCommand.RED_3,
    "Pink": BulbCommand.RED_4,
    "Green": BulbCommand.GREEN_1,
    "Lime": BulbCommand.GREEN_2,
    "Amber": BulbCommand.GREEN_3,
    "Yellow": BulbCommand.GREEN_4,
    "Blue": BulbCommand.BLUE_1,
    "Sky Blue": BulbCommand.BLUE_2,
    "Light Blue": BulbCommand.BLUE_3,
    "White": BulbCommand.WHITE,
    "Flash": BulbCommand.FLASH,
    "Smooth": BulbCommand.SMOOTH,
}

EFFECT_LIST: list[str] = list(EFFECT_TO_BUTTON.keys())
