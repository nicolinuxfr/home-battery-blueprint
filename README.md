# home-battery-blueprint

Localized Home Assistant blueprint project for steering up to four batteries from a single house power sensor. The blueprint focuses on discharge, can absorb real export through opportunistic charging, and writes a signed power target for each battery into a numeric entity. Optional custom actions remain available for integrations that also need a separate mode or service call. Each battery is grouped in its own collapsed section by default to keep the form compact.

This blueprint is intentionally generic. It does not try to normalize brand-specific APIs. Instead, each enabled battery slot is driven by:

- a signed numeric target entity updated by the blueprint
- optional custom actions for charge and/or discharge when an integration needs a separate mode switch
- either a signed helper or a direct device entity, depending on what the integration actually accepts

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fhome-battery-blueprint%2Fgh-pages%2Fen%2Fhome_battery_manager.yaml)

Raw import URL:

`https://raw.githubusercontent.com/nicolinuxfr/home-battery-blueprint/gh-pages/en/home_battery_manager.yaml`

## Configuration

- `House power sensor`: the main sensor used by the allocator. The selector only shows power sensors, but Home Assistant cannot filter the unit here, so you should still pick a signed sensor in `W` with `import > 0` and `export < 0`.
- `Blocking entities`: optional list of `binary_sensor` or `input_boolean` entities. The blueprint runs only if every selected entity is `off`. If one becomes `on`, `unknown`, or `unavailable`, the blueprint may write `0` once to neutralize managed batteries on that exact blocker state change, then it stops all custom actions and ignores later blocked runs until every blocker is back to `off`.

For each battery slot:

- `State of charge sensor`: leaving it empty disables the slot. The selector only shows battery sensors that report a percentage. If you fill it, the slot must also expose a numeric target entity and at least one non-zero power limit.
- `Maximum discharge power` and `Maximum charge power`: manual limits used by the allocator.
- `Priority on discharge`: prioritized batteries discharge first; opportunistic charging prefers non-priority batteries first. Without any extra option, a battery that reaches `90%` state of charge is also treated as temporarily priority so the allocator starts creating headroom before `100%`; while that battery stays active, this temporary priority is only released below `80%`.
- `Target power entity`: the `number` or `input_number` entity written by the blueprint. The target is signed: positive for discharge, negative for charge, `0` for stop. If charging is enabled, the selected entity must accept negative values.
- `Actual power sensor`: optional power sensor that reports the battery's real output. The blueprint keeps using the target entity and the house meter as its primary control loop, then uses this sensor as a delayed secondary correction when the reading stays fresh and a non-priority battery is still delivering materially less than its active target after the response grace period. During discharge, fresh telemetry from a priority battery can also confirm that it is still ramping so a lower-priority battery with a shorter cooldown may keep helping temporarily until the priority battery catches up. A priority battery is never trimmed down during discharge, but fresh telemetry can still reveal that it is already delivering more than its signed target.
- `Command cooldown`: per-battery delay between active target updates, and also the expected reaction window used by the discharge allocator. Lower values are treated as more reactive. Set it to `0` to disable the delay entirely. Writing `0` and flipping the sign still happen immediately so the blueprint can stop or reverse a battery without waiting. While one battery is cooling down, the allocator keeps its current active target reserved, and a lower-priority battery with a shorter cooldown may temporarily help during discharge until the slower priority battery catches up.
- `Discharge actions` and `Charge actions`: optional hooks executed on every active update in the matching direction. They receive runtime variables such as `battery_slot`, `battery_soc`, `target_power_w`, `target_discharge_w`, `target_charge_w`, `house_power_w` and `export_surplus_w`.

Zendure example:

- create a signed helper such as `input_number.zendure_virtual_p1`
- point the Zendure integration `p1meter` option to that helper
- set that helper as the `Target power entity`
- leave `Discharge actions` and `Charge actions` empty if the Zendure integration already consumes that helper directly

## How It Works

- The blueprint chooses one exclusive operating mode per run: `discharge`, `charge`, or `neutral`.
- It now also fires a structured `home_battery_blueprint_run` event on every run before any early stop or per-slot write. That event includes the trigger source, decision reason, operating mode, house power figures, computed targets, assist state, validation errors, and a JSON snapshot of every battery slot with current target, desired signed target, actual power, cooldown lock state, and which writes or custom actions were planned.
- Runs triggered by the house power sensor now ignore attribute-only updates, and they also stop early when the numeric delta stays below an internal `10 W` threshold. Blocking entities still bypass that threshold and keep triggering immediately.
- During discharge it allocates `max(house_power, 0)` across batteries, prioritizing flagged batteries first and then sorting by highest state of charge. Independently from the user-facing priority flag, a battery that reaches `90%` state of charge is also promoted temporarily so the allocator creates headroom before the battery hits `100%`; while that battery stays active, this promotion is only released below `80%`. If a priority battery is still ramping and reports fresh actual power, a lower-priority battery with a shorter cooldown can temporarily help until that priority battery catches up.
- The allocator rebuilds the underlying house demand from the net house meter by adding back the signed targets already active on managed batteries. This prevents the house sensor from cancelling out the batteries' own work and avoids depending on slow vendor telemetry.
- When an optional actual power sensor is configured and stays fresh, the blueprint can use it as a delayed secondary correction after the response grace period to notice that a non-priority battery is materially under-delivering compared with its active target. This correction never replaces the primary target-plus-house-meter control loop. During discharge it never trims a priority battery down, but it can still raise that priority battery's effective contribution when telemetry shows it is already delivering more than its signed target.
- If a priority battery has an active discharge target but fresh telemetry shows it is effectively no longer delivering after the response grace period, that battery temporarily stops being treated as priority so the remaining batteries are ordered only by their remaining state of charge.
- During cooldown or telemetry latency, the blueprint therefore keeps reasoning from the active target and the observed net house consumption instead of waiting for slow or irregular battery telemetry to catch up.
- When a battery has just received a new target, the blueprint now keeps that requested power reserved for the duration of its response grace period, while reconstructing house demand from measured battery output when fresh telemetry is available. If a slower priority battery is still ramping during that cooldown-derived reaction window, the allocator can also let a lower-priority battery with a shorter cooldown temporarily cover the observed gap until the priority battery catches up.
- If the raw house meter already shows meaningful export during discharge, the blueprint now trims discharge targets back down even during cooldown, releasing non-priority discharge first and only keeping as much reserved discharge as the raw meter still supports. This prevents stale reserved power from sustaining large exports for a whole cooldown window.
- To monitor the main side effect of that temporary assist, the blueprint now fires a `home_battery_blueprint_assist_overshoot` event whenever assist power is active and the raw house meter already reports meaningful export. The event includes the current house power, reconstructed demand, assist watts, helper slots, priority slots still ramping, discharge targets, and actual battery discharge readings.
- During opportunistic charging it now reacts to any real export that remains after subtracting the managed batteries' own discharge contribution, then fills charge-capable batteries from the lowest state of charge upward, avoiding discharge-priority batteries until needed. This keeps the batteries from charging each other while still absorbing export instead of sending it to the grid.
- A fixed internal `60 W` command deadband filters tiny meter oscillations, and a fixed `80 W` release threshold keeps an already active battery in place until the opposite flow becomes more meaningful. Together they reduce flip-flopping around `0 W` without exposing extra tuning knobs while staying closer to zero.
- In the `neutral` deadband, the blueprint now keeps the current contribution of managed batteries instead of immediately falling back to `0`. This avoids rapid on/off cycling when a battery has just offset almost all of the house demand.
- The target written by the blueprint is signed: positive for discharge, negative for charge, `0` for neutral. Writing `0`, reacting to an invalid sensor, honoring a blocking entity, or flipping the sign all happen immediately without waiting for the cooldown. During an active cooldown, the blueprint still reserves the already-commanded power on that battery by default, but a significant raw export now allows a same-direction discharge reduction before the cooldown expires.
- Restarting a battery from `0` back to the same direction no longer bypasses the cooldown. This avoids rapid flapping where a priority battery is released to let another one help, then immediately retakes the load on the next sensor update.
- If one target entity rejects an update, for example because the integration enforces its own minimum change delay, the automation now keeps going and still updates the other battery slots.
- Validation now runs before any per-battery write or custom action. Every non-zero command is rechecked against the current blocking entities right before execution, and a blocked `0` write is allowed only on the blocker state change itself.
- Optional charge and discharge actions only run while the battery is active in the matching direction. They are useful for integrations that still need a `select`, an auxiliary service call, or a helper-to-vendor translation layer.
- Internal automation steps now carry explicit names so Home Assistant traces show per-battery target writes, charge/discharge hooks, and validation stops more clearly during debugging.
- If an enabled slot is incomplete, the automation stops with an explicit validation error that tells you whether the target entity is missing or both power limits are `0 W`.

## Known Limitations

- The blueprint does not create a moving-average helper. If you want a smoothed house signal, provide an already filtered sensor as input.
- If a battery should charge, the chosen target entity must accept negative values. Otherwise, use an intermediate signed helper.
- Optional actions do not run in neutral. If your integration needs an explicit translation of `0`, use a signed helper that the integration or another automation consumes.
- The blueprint metadata and documentation point to `nicolinuxfr/home-battery-blueprint`.

## 24h Log Capture

The simplest way to send back a usable history is to capture `home_battery_blueprint_run` events into a JSONL file.

A ready-to-copy Home Assistant package is provided in [examples/home_battery_blueprint_diagnostics_package.yaml](/Users/nicolas/Developer/domotique/home-battery-blueprint/examples/home_battery_blueprint_diagnostics_package.yaml).

Steps:

1. Enable Home Assistant `packages` if you do not already use them:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. Copy [examples/home_battery_blueprint_diagnostics_package.yaml](/Users/nicolas/Developer/domotique/home-battery-blueprint/examples/home_battery_blueprint_diagnostics_package.yaml) to `/config/packages/home_battery_blueprint_diagnostics.yaml`.
3. Restart Home Assistant.
4. Let it run for 24 hours.
5. Grab `/config/home_battery_blueprint_runs.jsonl` and send it back.

Tips:

- Delete `/config/home_battery_blueprint_runs.jsonl` before a new capture window so you start clean.
- The file contains one JSON line per blueprint run, which makes it easy to filter or compress before sharing.
