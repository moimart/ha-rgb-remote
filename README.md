# RGB IR Remote Bulb — Home Assistant custom integration

Drive a cheap 24-key Chinese RGB GU10 / strip bulb from Home Assistant via any
IR transmitter exposed under the new (HA 2026.4+) `infrared` entity platform —
for example a Broadlink RM4 / RM4 Pro or an ESPHome IR blaster.

The integration ships the standard 24-key NEC code table (address `0xF7`).
Each bulb is one config entry. Add the integration once per bulb and pick which
transmitter should drive it, so multi-room setups with several Broadlinks work
out of the box.

## Requirements

- Home Assistant core **≥ 2026.4**
- An IR transmitter integration set up and exposing an `infrared.*` entity
  (Broadlink RM4 / RM4 Pro / RM Mini, ESPHome with `remote_transmitter`, …)

## Install — Manual copy

1. Copy `custom_components/rgb_ir_remote/` into `<config>/custom_components/` on
   your HA host (Samba, SSH, or File Editor add-on).
2. **Settings → System → Restart Home Assistant**.
3. **Settings → Devices & Services → + Add Integration → "RGB IR Remote Bulb"**.
4. Name the bulb and pick the IR transmitter that has line-of-sight to it.
5. Repeat step 3 for every additional bulb.

## Install — HACS custom repository

1. Push this repo to your own GitHub (e.g. `moimart/ha-rgb-remote`).
2. In HACS: ⋮ → **Custom repositories** → URL = your repo, category =
   **Integration** → Add.
3. Install "RGB IR Remote Bulb", restart HA, then follow steps 3–5 above.

## What the entity exposes

- `light.<bulb_name>` with **on/off**, **brightness** (10 buckets, dead-
  reckoned — see below), and an **effect list** for every coloured button on
  the remote plus the four animation modes (Flash / Strobe / Fade / Smooth).
- `assumed_state` is **true** — the bulb has no feedback channel, so any
  change from the physical remote or a power cycle will leave HA's state
  stale until you re-issue a command.

## How brightness works

Cheap 24-key RGB bulbs only expose **±** brightness buttons. The integration
maps HA's 0–255 brightness onto 10 internal steps and presses the appropriate
button N times to reach the target, dead-reckoning the current step.

Two implications:

- Selecting any effect or turning the bulb on **resets the bulb to max
  brightness**, which the integration reflects in its internal counter.
- If you press the physical remote, HA's internal counter drifts. Use the
  effect list to "anchor" state by reselecting a colour.

## Different remote?

If your bulb doesn't respond, two ways to diagnose:

1. **Use Broadlink to learn one button** (e.g. *On*) via the
   `remote.learn_command` service. Decode the captured code (try
   [Tasmota's IRremote ESP8266 decoder](https://tasmota.github.io/docs/Codes-for-IR-Remotes/)
   or `irrecord`). If the protocol is still NEC but the address differs,
   change `ADDRESS` in `codes.py`. If individual buttons differ, edit the
   `BulbCommand` enum values.
2. **Wrong protocol entirely?** Some clones use NEC2 or non-NEC protocols.
   Subclass a different encoder from `infrared_protocols.commands` and swap
   `BulbCommand.to_command()` accordingly.

## Files

- `manifest.json` — integration metadata and the `infrared-protocols`
  PyPI dependency.
- `codes.py` — the 24-key NEC code table and helpers.
- `config_flow.py` — picks one IR transmitter from the available emitters.
- `light.py` — the `LightEntity` with brightness dead-reckoning + effects.
- `__init__.py` — config entry plumbing.

## License

MIT.
