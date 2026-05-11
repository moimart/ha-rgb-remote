"""NEC code table for the 24-key Chinese RGB bulb remote.

v0.1.2 — SMOKE-TEST BUILD for the "Practical Series II" GU10 RGB bulb.

Only the GREEN_1 button (`address=0x00, command=0x18`) has been captured
and verified against an actual bulb. All other command bytes below are the
WoodUino 24-key reference values and are *probably wrong* for this bulb
factory — they're left in place so the integration loads, but only the
"Green" effect is exposed in EFFECT_TO_BUTTON until the rest are captured.

If your remote does not respond to the green code, capture one button with
the Broadlink `remote.learn_command` service, decode it (e.g. with `irdb`
or `rtl_433`), and replace the address constant or command byte below.
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
    """24-key RGB bulb remote command codes (command byte of NEC frame).

    Only entries flagged VERIFIED below have been confirmed on the
    Practical Series II bulb. The others are placeholders from the
    common 24-key reference table — left in so the entity loads, but
    not exposed via EFFECT_TO_BUTTON yet.
    """

    # --- UNVERIFIED placeholders (probably wrong for Practical Series II) ---
    BRIGHTNESS_UP = 0x00
    BRIGHTNESS_DOWN = 0x80
    OFF = 0x40
    ON = 0xC0

    RED_1 = 0x20
    # --- VERIFIED ---
    GREEN_1 = 0x18  # captured from Practical Series II
    # --- UNVERIFIED ---
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


# Effect list reduced to verified codes only for v0.1.x smoke test.
# Add more entries here as you capture and confirm them.
EFFECT_TO_BUTTON: dict[str, BulbCommand] = {
    "Green": BulbCommand.GREEN_1,
}

EFFECT_LIST: list[str] = list(EFFECT_TO_BUTTON.keys())
