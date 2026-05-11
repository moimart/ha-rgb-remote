# PRD — RGB IR Remote Bulb integration for Home Assistant

**Status:** v0.1 implemented · author: @moimart · last updated: 2026-05-11

## 1. Problem

Cheap "24-key" Chinese RGB GU10 / strip bulbs (Practical Series II and
near-identical clones) are sold by the millions but only ship with a one-way
IR remote. They have no Wi-Fi, no Zigbee, no app, no feedback channel. Owners
who already have a Home Assistant setup with an IR blaster (Broadlink RM4 Pro,
ESPHome with an IR LED, etc.) currently have to glue these bulbs into HA via
ad-hoc `script` entities calling `remote.send_command` with opaque base64
blobs. The result is unmaintainable, non-portable across blasters, and offers
no real `light` entity in the UI.

Home Assistant 2026.4 introduced the `infrared` entity platform, which
decouples IR-emitter hardware from the devices it controls. This makes it
possible — for the first time — to ship a clean, portable consumer integration
for these bulbs that works with any IR transmitter the user happens to have.

## 2. Goals

- **G1** Expose every 24-key RGB IR bulb as a first-class `light.<name>`
  entity in Home Assistant with on/off, brightness, and an effect list that
  covers every button on the physical remote.
- **G2** Work with *any* HA IR transmitter on the new platform — Broadlink
  RM4 / RM4 Pro / RM Mini today; ESPHome IR blasters once they expose
  `infrared.*` entities; future transmitters with zero code changes.
- **G3** Multi-bulb, multi-transmitter friendly: one config entry per bulb;
  user picks which IR emitter drives that bulb during the config flow.
- **G4** Codes live in a portable symbolic form (NEC address + command bytes
  via `infrared-protocols`), not as transmitter-specific blobs.
- **G5** Survive HA restarts without losing assumed power/effect/brightness
  state.

## 3. Non-goals

- **NG1** Support for "44-key" remotes (DIY1–6, separate RGB intensity, jump
  modes). Future work — would extend the code table and effect list.
- **NG2** Receive / learn mode. The 2026.5 RF platform's roadmap explicitly
  defers receive to a later release; the IR platform doesn't yet support it
  for consumer integrations either. Initial code capture is a manual step.
- **NG3** True colour control via `hs_color` / `rgb_color`. The bulb's
  hardware exposes 16 preset colours, not a continuous gamut — pretending
  otherwise would mislead automations.
- **NG4** Multiple-bulb addressing on a single remote channel. These bulbs
  have no per-unit address, so every bulb in IR range of the blaster reacts
  to every press. A "group of two bulbs" is a single config entry.
- **NG5** Per-device cloud/telemetry. Offline-only by design.

## 4. Users and personas

| Persona | Need |
|---|---|
| **Sam — HA tinkerer with a Broadlink** | Has 3–5 of these bulbs scattered around the house. Wants them in dashboards and automations without writing YAML scripts. Already runs HA 2026.4+. |
| **Pat — HACS curator** | Discovers the repo through HACS custom-repository search. Expects one-click install, sensible defaults, and a README that explains the dead-reckoning caveat up front. |
| **Lee — multi-room user** | Owns two Broadlinks in different rooms. Needs a way to bind each bulb to the blaster that has line-of-sight to it. Will not tolerate a global "default transmitter" setting. |

## 5. Functional requirements

### FR-1 — Config flow
- Single step, two fields: `name` (string), `transmitter` (entity selector,
  filtered to `infrared.*` entities returned by `async_get_emitters`).
- Abort with `no_emitters` if HA has no IR transmitters configured.
- Unique-id = `<transmitter>::<name.lower()>`; reject duplicates with the
  standard `already_configured` abort.
- Re-adding a bulb after a transmitter rename surfaces as a new entry; the
  old one becomes orphaned (acceptable; user can delete).

### FR-2 — Light entity capabilities
- `supported_color_modes = {ColorMode.BRIGHTNESS}`, `color_mode = BRIGHTNESS`.
- `supported_features = LightEntityFeature.EFFECT`.
- `assumed_state = True`, `should_poll = False`.
- `effect_list` contains 16 named colours (one per coloured button on the
  remote) + four animations: Flash, Strobe, Fade, Smooth.
- Effect names are stable across releases (used in automations).

### FR-3 — Command transport
- All transmissions go through
  `homeassistant.components.infrared.async_send_command(hass, entity_id, command)`.
- Each command is a `NECCommand(address=0xF7, command=<byte>)` from
  `infrared_protocols.commands.nec`. No raw timings stored locally.
- A single `asyncio.Lock` per entity serialises sends so concurrent automation
  calls don't garble frames.
- Consecutive presses (brightness ramp, effect+brightness in one call) are
  spaced by 120 ms so the receiver can decode each frame independently.

### FR-4 — Brightness model
- Ten internal buckets (1..10) mapped from HA's 0..255 range.
- Each `BR+ / BR-` press shifts one bucket; integration sends
  `|target - current|` presses to reach the target.
- Power-on or effect selection resets the internal counter to 10 (matches
  observed bulb behaviour after pressing On or a colour).
- Physical-remote presses cause drift; reselecting an effect is the
  documented recovery.

### FR-5 — State persistence
- `RestoreEntity` integration: power state, last effect, and brightness are
  restored on HA restart.
- No external storage; HA's recorder-backed state is the source of truth.

### FR-6 — Internationalisation
- `strings.json` + `translations/en.json` present. Other locales accepted via
  PRs but not shipped in v0.1.

## 6. Non-functional requirements

- **NFR-1** Pure-Python. Single PyPI dependency: `infrared-protocols>=4.0.0`.
- **NFR-2** Compatible with HA Core ≥ **2026.4** (manifest enforces).
- **NFR-3** Distributable as a HACS custom repository (`hacs.json` present;
  `render_readme: true`).
- **NFR-4** No I/O outside `async_send_command`. No network, no disk writes
  beyond HA's own state recorder.
- **NFR-5** All code passes Ruff + basedpyright at the same strictness as
  HA core's `custom_components/` policy.

## 7. Architecture (one screen)

```
  HA UI                  this integration               infrared platform
  ┌────────┐             ┌──────────────────┐          ┌───────────────────┐
  │ light. │── turn_on ─▶│ RgbIrBulb        │── send ─▶│ async_send_command│
  │ <bulb> │             │  + brightness    │  command │     │             │
  └────────┘             │    dead-reckon   │          │     ▼             │
                         │  + effect map    │          │ Broadlink / ESPHome│
                         │  + RestoreEntity │          │  IR emitter entity │
                         └────────┬─────────┘          └───────────────────┘
                                  │ NECCommand
                                  ▼
                     ┌────────────────────────┐
                     │ infrared_protocols     │
                     │  .commands.nec         │  ← PyPI dep, 38 kHz NEC
                     └────────────────────────┘
```

## 8. Out-of-scope and future work

| Idea | Trigger to revisit |
|---|---|
| 44-key remote support | A user reports a non-respond bulb that turns out to be the 44-key variant |
| `hs_color` approximation by mapping nearest preset | Automation user asks "why can't I use a colour picker" |
| ESPHome learning helper | Once the IR platform exposes receive support |
| Per-bulb groups (one entry → multiple lights) | Several users report co-located bulbs that share a code |
| YAML import of legacy `remote.send_command` scripts | HACS install reviews mention migration pain |
| RF (433 MHz) sibling integration for the RF variant of the same bulb family | If a user confirms an RF-controlled clone exists |

## 9. Open questions

- **OQ-1** Does `claude.ai_HASS`-discovered `infrared.broadlink_ir_emitter`
  enumerate both of the user's Broadlinks, or only one? Verifying this on a
  real two-blaster setup before the v0.1 GitHub release.
- **OQ-2** Should "anchor brightness" be a service call (`rgb_ir_remote.resync`)
  that sends 10× `BR-` to force the bulb to min, then ramps back up to the
  desired bucket? Cleaner state at the cost of a visible flicker.
- **OQ-3** Effect-name palette: lock in v0.1 names (Red / Green / Blue /
  White / Orange / Lime / …) before any user has an automation depending on
  them, to avoid future renaming churn.

## 10. Risks

- **R-1 — Wrong address byte for some clones.** Mitigation: README documents
  the capture-and-patch workflow; address is one constant in `codes.py`.
- **R-2 — `infrared-protocols` API churn.** Currently v4.0.0; library is new
  and may break compatibility. Mitigation: pin lower bound in manifest;
  tested upper bound bumped in CI when released.
- **R-3 — IR range / line-of-sight failures.** Out of the integration's
  control. Mitigation: README recommends one transmitter per room and
  documents the multi-transmitter config flow as the answer.
- **R-4 — State drift from physical remote use.** Documented limitation;
  recoverable by reselecting an effect. No good technical mitigation without
  a receive channel.

## 11. Acceptance criteria for v0.1

1. Fresh HA 2026.4 instance + Broadlink RM4 Pro: integration installs, config
   flow shows the IR emitter, bulb appears as a `light` entity.
2. Pressing the entity's on/off, brightness slider, and effect selector each
   produce a visible bulb response.
3. Restarting HA preserves the last effect and brightness on the entity.
4. Two Broadlinks present → config flow lets you pick either, and each bulb's
   commands route only through its chosen emitter.
5. Code passes Ruff + basedpyright with HA-core defaults.
