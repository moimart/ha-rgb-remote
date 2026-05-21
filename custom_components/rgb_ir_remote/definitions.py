"""Constants for the RGB IR Remote Bulb integration.

This module lives separately from ``const.py`` because HACS has
repeatedly failed to overwrite ``const.py`` during updates on this
repo — leaving users with an integration that won't load because
new constants are missing. A fresh filename has no HACS cache entry,
forcing a clean download every time.
"""

from __future__ import annotations

DOMAIN = "rgb_ir_remote"

CONF_TRANSMITTER = "transmitter"
CONF_NAME = "name"
CONF_REMOTE_TYPE = "remote_type"

# Stable IDs used in config-entry storage. Don't rename without a migration.
REMOTE_TYPE_GENERIC_1 = "generic_1"
REMOTE_TYPE_LEDLAMP = "ledlamp"

BRIGHTNESS_STEPS = 10
