"""NEC code table for the 24-key Chinese RGB bulb remote.

All buttons share address 0xF7; only the command byte differs. The encoder
auto-computes the inverted address and command bytes, so we pass the raw
command byte directly.

If your remote does not respond to these codes, capture one button with the
Broadlink `remote.learn_command` service, decode it (e.g. with `irdb` or
`rtl_433`), and replace the address constant below.
"""

from __future__ import annotations

from enum import IntEnum

try:
    # infrared-protocols >= 3.0 — split into commands/ subpackage
    from infrared_protocols.commands.nec import NECCommand
except ImportError:
    # infrared-protocols == 2.0.0 (shipped with HA 2026.4/2026.5) — flat module
    from infrared_protocols.commands import NECCommand  # type: ignore[no-redef]

ADDRESS = 0xF7


class BulbCommand(IntEnum):
    """24-key RGB bulb remote command codes (command byte of NEC frame)."""

    BRIGHTNESS_UP = 0x00
    BRIGHTNESS_DOWN = 0x80
    OFF = 0x40
    ON = 0xC0

    RED_1 = 0x20
    GREEN_1 = 0xA0
    BLUE_1 = 0x60
    WHITE = 0xE0

    RED_2 = 0x10
    GREEN_2 = 0x90
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


EFFECT_TO_BUTTON: dict[str, BulbCommand] = {
    "Red": BulbCommand.RED_1,
    "Green": BulbCommand.GREEN_1,
    "Blue": BulbCommand.BLUE_1,
    "White": BulbCommand.WHITE,
    "Orange": BulbCommand.RED_2,
    "Lime": BulbCommand.GREEN_2,
    "Sky Blue": BulbCommand.BLUE_2,
    "Yellow": BulbCommand.RED_3,
    "Turquoise": BulbCommand.GREEN_3,
    "Indigo": BulbCommand.BLUE_3,
    "Pale Yellow": BulbCommand.RED_4,
    "Mint": BulbCommand.GREEN_4,
    "Purple": BulbCommand.BLUE_4,
    "Cream": BulbCommand.RED_5,
    "Aqua": BulbCommand.GREEN_5,
    "Pink": BulbCommand.BLUE_5,
    "Flash": BulbCommand.FLASH,
    "Strobe": BulbCommand.STROBE,
    "Fade": BulbCommand.FADE,
    "Smooth": BulbCommand.SMOOTH,
}

EFFECT_LIST: list[str] = list(EFFECT_TO_BUTTON.keys())
