"""NEC code table for the Practical Series II GU10 RGB bulb.

Captured against the user's actual hardware on 2026-05-11 with a Broadlink
RM4 Pro. The bulb uses standard NEC at 38 kHz with address 0x00.

VERIFIED (captured + decoded with valid NEC inverse-byte checksums):
    address       = 0x00
    BRIGHTNESS_UP = 0x15
    BRIGHTNESS_DOWN = 0x09
    ON            = 0x45
    RED_1         = 0x16
    GREEN_2       = 0x18  (the "Lime" — row-2 green, below the main "G")

UNVERIFIED (placeholders from the WoodUino 24-key reference table; left in
so the enum loads but kept out of EFFECT_TO_BUTTON):
    OFF, GREEN_1, BLUE_1, WHITE,
    RED_2, BLUE_2, FLASH,
    RED_3, GREEN_3, BLUE_3, STROBE,
    RED_4, GREEN_4, BLUE_4, FADE,
    RED_5, GREEN_5, BLUE_5, SMOOTH

The four buttons captured but garbled on the first pass (off, green_1,
blue_1, white) need re-learning — the Broadlink missed the NEC leader
pulse on those, so the bytes decoded as noise. Re-learn them and we can
expose the full main-colour row.
"""

from __future__ import annotations

from enum import IntEnum

try:
    # infrared-protocols >= 3.0 — split into commands/ subpackage
    from infrared_protocols.commands.nec import NECCommand
except ImportError:
    # infrared-protocols == 2.0.0 (shipped with HA 2026.4/2026.5) — flat module
    from infrared_protocols.commands import NECCommand  # type: ignore[no-redef]

# VERIFIED for Practical Series II GU10 bulb (captured 2026-05-11)
ADDRESS = 0x00


class BulbCommand(IntEnum):
    """RGB bulb remote command codes (command byte of NEC frame).

    See module docstring for which entries are VERIFIED vs UNVERIFIED.
    """

    # --- VERIFIED ---
    BRIGHTNESS_UP = 0x15
    BRIGHTNESS_DOWN = 0x09
    ON = 0x45
    RED_1 = 0x16
    GREEN_2 = 0x18  # the row-2 "Lime" green
    # --- UNVERIFIED (recapture pending) ---
    OFF = 0x40
    GREEN_1 = 0xA0
    BLUE_1 = 0x60
    WHITE = 0xE0
    # --- UNVERIFIED placeholders (rest of the colour rows) ---
    RED_2 = 0x10
    BLUE_2 = 0x50
    FLASH = 0xD0

    RED_3 = 0x30
    GREEN_3 = 0xB0
    BLUE_3 = 0x70
    STROBE = 0xF0

    RED_4 = 0x08
    GREEN_4 = 0x88
    BLUE_4 = 0x48
    FADE = 0xC8

    RED_5 = 0x28
    GREEN_5 = 0xA8
    BLUE_5 = 0x68
    SMOOTH = 0xE8

    def to_command(self, repeat_count: int = 0) -> NECCommand:
        """Build the NECCommand for this button press."""
        return NECCommand(
            address=ADDRESS,
            command=self.value,
            repeat_count=repeat_count,
        )


# Only effects backed by VERIFIED command bytes are exposed.
# Add more entries here as you capture and confirm them.
EFFECT_TO_BUTTON: dict[str, BulbCommand] = {
    "Red": BulbCommand.RED_1,
    "Lime": BulbCommand.GREEN_2,
}

EFFECT_LIST: list[str] = list(EFFECT_TO_BUTTON.keys())
