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
- `Priority on discharge`: prioritized batteries discharge first; opportunistic charging prefers non-priority batteries first.
- `Target power entity`: the `number` or `input_number` entity written by the blueprint. The target is signed: positive for discharge, negative for charge, `0` for stop. If charging is enabled, the selected entity must accept negative values.
- `Actual power sensor`: optional power sensor that reports the battery's real output. The blueprint keeps using the target entity and the house meter as its primary control loop, then uses this sensor only as a delayed secondary correction when the reading stays fresh and a non-priority battery is still delivering materially less than its active target after the response grace period. A priority battery is never trimmed down during discharge, but fresh telemetry can still reveal that it is already delivering more than its signed target.
- `Command cooldown`: per-battery anti-spam delay for active target updates. Set it to `0` to disable it. Writing `0` and flipping the sign still happen immediately so the blueprint can stop or reverse a battery without waiting. While one battery is cooling down, the allocator keeps its current active target and redistributes only the remaining demand or export surplus to the other batteries.
- `Discharge actions` and `Charge actions`: optional hooks executed on every active update in the matching direction. They receive runtime variables such as `battery_slot`, `battery_soc`, `target_power_w`, `target_discharge_w`, `target_charge_w`, `house_power_w` and `export_surplus_w`.

Zendure example:

- create a signed helper such as `input_number.zendure_virtual_p1`
- point the Zendure integration `p1meter` option to that helper
- set that helper as the `Target power entity`
- leave `Discharge actions` and `Charge actions` empty if the Zendure integration already consumes that helper directly

## How It Works

- The blueprint chooses one exclusive operating mode per run: `discharge`, `charge`, or `neutral`.
- During discharge it allocates `max(house_power, 0)` across batteries, prioritizing flagged batteries first and then sorting by highest state of charge.
- The allocator rebuilds the underlying house demand from the net house meter by adding back the signed targets already active on managed batteries. This prevents the house sensor from cancelling out the batteries' own work and avoids depending on slow vendor telemetry.
- When an optional actual power sensor is configured and stays fresh, the blueprint can use it as a delayed secondary correction after the response grace period to notice that a non-priority battery is materially under-delivering compared with its active target. This correction never replaces the primary target-plus-house-meter control loop. During discharge it never trims a priority battery down, but it can still raise that priority battery's effective contribution when telemetry shows it is already delivering more than its signed target.
- If a priority battery has an active discharge target but fresh telemetry shows it is effectively no longer delivering after the response grace period, that battery temporarily stops being treated as priority so the remaining batteries are ordered only by their remaining state of charge.
- During cooldown or telemetry latency, the blueprint therefore keeps reasoning from the active target and the observed net house consumption instead of waiting for slow or irregular battery telemetry to catch up.
- During opportunistic charging it looks for real export, requires at least one battery at `99%` or above, and then fills charge-capable batteries from the lowest state of charge upward, avoiding discharge-priority batteries until needed.
- A fixed internal `60 W` command deadband filters tiny meter oscillations, and a fixed `80 W` release threshold keeps an already active battery in place until the opposite flow becomes more meaningful. Together they reduce flip-flopping around `0 W` without exposing extra tuning knobs while staying closer to zero.
- In the `neutral` deadband, the blueprint now keeps the current contribution of managed batteries instead of immediately falling back to `0`. This avoids rapid on/off cycling when a battery has just offset almost all of the house demand.
- The target written by the blueprint is signed: positive for discharge, negative for charge, `0` for neutral. Writing `0`, reacting to an invalid sensor, honoring a blocking entity, or flipping the sign all happen immediately without waiting for the cooldown. During an active cooldown, the blueprint reserves the already-commanded power on that battery and reallocates only the remaining unmet load or export to the other batteries.
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
