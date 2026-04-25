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
- `Blocking entities`: optional list of `binary_sensor` or `input_boolean` entities. The blueprint runs only if every selected entity is `off`. If one becomes `on`, `unknown`, or `unavailable`, the blueprint may write `0` once to neutralize managed batteries on that exact blocker state change, then all house-power-triggered runs are ignored until every blocker is back to `off`. This lets an external off-peak charging automation control the same batteries while the blueprint is blocked.

For each battery slot:

- `State of charge sensor`: leaving it empty disables the slot. The selector only shows battery sensors that report a percentage. If you fill it, the slot must also expose a numeric target entity and at least one non-zero power limit.
- `Maximum discharge power` and `Maximum charge power`: manual limits used by the allocator.
- `Target power entity`: the `number` or `input_number` entity written by the blueprint. The target is signed: positive for discharge, negative for charge, `0` for stop. If charging is enabled, the selected entity must accept negative values.
- `Actual power sensor`: optional power sensor that reports the battery's real output. The blueprint keeps using the target entity and the house meter as its primary control loop. After the response grace period, a valid non-stale reading is used only as a guardrail to avoid counting a battery as real supply when it no longer delivers. A stale reading does not prevent an idle battery from starting. If telemetry stays stale after an active target had time to react, that battery is kept out of extra discharge allocation while its already active target can stay in place unless a stop, sign change, or real export requires changing it.
- `Command cooldown`: per-battery delay between active target updates, and the main signal used to determine how reactive a battery is. Lower values make a battery handle residual changes first. Higher values make it keep a steadier active target while faster batteries absorb demand changes. Set it to `0` to disable the delay entirely. Writing `0`, flipping the sign, and starting from `0` when the raw house meter confirms matching import or export still happen immediately so the blueprint can stop, reverse, or resume a useful battery without waiting. A significant raw export can also reduce an active discharge target before the cooldown expires.
- `Discharge actions` and `Charge actions`: optional hooks executed on every active update in the matching direction. They receive runtime variables such as `battery_slot`, `battery_soc`, `target_power_w`, `target_discharge_w`, `target_charge_w`, `house_power_w` and `export_surplus_w`.

Zendure example:

- create a signed helper such as `input_number.zendure_virtual_p1`
- point the Zendure integration `p1meter` option to that helper
- set that helper as the `Target power entity`
- leave `Discharge actions` and `Charge actions` empty if the Zendure integration already consumes that helper directly

## How It Works

- The blueprint chooses one exclusive operating mode per run: `discharge`, `charge`, or `neutral`.
- It now also fires a structured `home_battery_blueprint_run` event on every allowed run before any early stop or per-slot write. That event includes the trigger source, decision reason, operating mode, house power figures, computed targets, cooldown state, validation errors, and a JSON snapshot of every battery slot with current target, desired signed target, actual power, actual power age, stale actual-power state, confirmed zero-start state, and which writes or custom actions were planned.
- House power values are accepted only when Home Assistant reports them as valid finite numbers. Non-numeric states, including `unknown`, `unavailable`, `NaN`, and infinity, are treated as an invalid sensor instead of being silently coerced to `0 W`.
- Runs triggered by the house power sensor now ignore attribute-only updates, and they also stop early when the numeric delta stays below an internal `10 W` threshold only if that run would otherwise be a true no-op. If a small delta still implies a target write or active custom action, the blueprint continues instead of skipping the run. Blocking entities still bypass that threshold and keep triggering immediately.
- During discharge, active targets are kept as the stable base first. Any remaining demand is assigned to available batteries ordered by shortest command cooldown, so responsive batteries handle the residual instead of moving long-cooldown batteries for every small change.
- Batteries at or above `90%` state of charge are promoted ahead of the normal residual order during discharge so they create headroom before reaching full charge. The same high-SoC batteries are released later during discharge reductions and filled later during opportunistic charging.
- When two batteries have the same cooldown, the higher-SoC battery can take over from a lower-SoC active battery instead of waiting behind its existing target.
- When demand drops, discharge is reduced in the opposite order: the shortest-cooldown batteries are released first. If real export remains, charge-capable batteries with the shortest cooldown can temporarily absorb that excess instead of waiting for slow integrations to accept their next target.
- The allocator rebuilds the underlying house demand from the net house meter by adding back each managed battery's effective contribution: the active target while no actual power sensor is configured or while the battery is still inside its response window, then the latest valid measured power while it is not stale. Configured telemetry that is non-numeric or very stale contributes `0` until the battery is restarted or reports a valid reading again.
- When an optional actual power sensor is configured, the blueprint uses it after the response grace period to notice that a battery is materially under-delivering compared with its active target. This correction never replaces the primary target-plus-house-meter control loop.
- If a battery has an active discharge target but valid non-stale telemetry shows it is effectively no longer delivering after the response grace period, or its configured actual power sensor stays stale after the response window, that battery is temporarily kept out of extra discharge allocation. Its active target can still be held for stability, but its measured contribution is not counted, so faster batteries can cover the residual. An idle battery with stale telemetry can still be started; the guardrail applies only after the target had time to produce an effect. The run log exposes this as `actual_power_usable`, `actual_power_stale`, `discharge_delivery_stalled` and `discharge_available`.
- During cooldown or telemetry latency, the blueprint therefore keeps reasoning from the active target and the observed net house consumption instead of waiting for slow or irregular battery telemetry to catch up.
- Each run captures a single timestamp and reuses it for target ages, actual-power ages, and per-slot cooldown checks. Charge and discharge cooldown gates share the same elapsed-time calculation before applying their direction-specific capability checks.
- When a battery has just received a new target, the blueprint keeps that requested power reserved for the duration of its response grace period, while faster batteries take only the remaining residual.
- If the raw house meter already shows meaningful export during discharge, the blueprint trims discharge targets back down even during cooldown, releasing the shortest-cooldown discharge first and only keeping as much reserved discharge as the raw meter still supports. This prevents stale reserved power from sustaining large exports for a whole cooldown window.
- When a fresh actual-power reading shows that a battery is still above a newly lower discharge allocation during its response window, the raw-export trim credits that pending drop before cutting the target further. This avoids over-reducing a responsive battery and creating a grid-import rebound, without relying on a second pre-cooldown write that cloud integrations may reject.
- If reallocation asks one battery to increase while another battery still needs to decrease but remains locked by cooldown, the increase is blocked only for the part that exceeds measured real import. The blueprint prefers a short grid import over an export spike caused by temporarily incompatible targets, without preventing an available battery from covering real house demand.
- The same raw-export trim also applies while holding an existing discharge target in the neutral deadband. If reducing every discharge target still leaves at least the `80 W` release threshold of raw export, the blueprint can temporarily use charge-capable batteries that are not still assigned a discharge target in that run to absorb the residual spike, preferring the shortest command cooldown first. The extra in-band responsive trim below that threshold only reduces active discharge; unused in-band trim does not trigger charging by itself.
- During opportunistic charging it reacts to any real export that remains after subtracting the managed batteries' own discharge contribution, then fills charge-capable batteries ordered by shortest cooldown and lowest state of charge. This keeps responsive batteries absorbing export instead of sending it to the grid.
- A fixed internal `60 W` command deadband filters tiny meter oscillations, and a fixed `80 W` release threshold keeps an already active slow battery in place until the opposite flow becomes more meaningful. If an active discharge battery has the shortest cooldown and that cooldown is `10 s` or less, it can still trim the remaining raw export inside this release band so responsive batteries keep the house closer to zero without moving slower batteries. Once a battery's own cooldown has elapsed, smaller raw export inside this release band can also trim that active discharge target instead of holding a known overshoot. Separately, the shortest available discharge or charge battery at `10 s` or less can receive small non-zero residual targets below the main command deadband, even if it is currently idle.
- A second internal `10 W` target deadband now skips same-direction target corrections below that threshold. This removes noisy micro-adjustments and duplicate custom-action runs when the requested power only moves by a few watts, while still allowing forced stops, sign flips, and export-guard discharge trims to go through immediately.
- In the `neutral` deadband, the blueprint now keeps the current contribution of managed batteries instead of immediately falling back to `0`. This avoids rapid on/off cycling when a battery has just offset almost all of the house demand.
- When the computed signed target rounds to the same value already present on the target entity, the blueprint now skips the redundant write and does not rerun same-direction custom actions. This reduces no-op service calls and duplicate integration side effects while preserving real target changes, sign flips, and forced stops.
- The target written by the blueprint is signed: positive for discharge, negative for charge, `0` for neutral. Writing `0`, reacting to an invalid sensor, honoring a blocking entity, flipping the sign, or starting from `0` while the raw house meter confirms the matching grid flow all happen immediately without waiting for the cooldown. During an active cooldown, the blueprint still reserves the already-commanded power on that battery by default, but a significant raw export allows a same-direction discharge reduction before the cooldown expires.
- Same-direction corrections on an already active battery still obey the cooldown unless they are small forced stops, sign changes, or export-guard discharge reductions. This avoids noisy target churn while still allowing an idle battery to resume when the house is genuinely importing from the grid.
- If one target entity rejects an update, for example because the integration enforces its own minimum change delay, the automation now keeps going and still updates the other battery slots.
- Validation now runs before any per-battery write or custom action. Every non-zero command is rechecked against the current blocking entities right before execution, and a blocked `0` write is allowed only on the blocker state change itself. Later house-power updates while blocked are rejected before actions start, so the blueprint does not fight external off-peak charging.
- Optional charge and discharge actions only run while the battery is active in the matching direction. They are useful for integrations that still need a `select`, an auxiliary service call, or a helper-to-vendor translation layer.
- Internal automation steps now carry explicit names so Home Assistant traces show per-battery target writes, charge/discharge hooks, and validation stops more clearly during debugging.
- If an enabled slot is incomplete, the automation stops with an explicit validation error that tells you whether the target entity is missing or both power limits are `0 W`.

## Known Limitations

- The blueprint does not create a moving-average helper. If you want a smoothed house signal, provide an already filtered sensor as input.
- If a battery should charge, the chosen target entity must accept negative values. Otherwise, use an intermediate signed helper.
- The shortest available responsive battery can receive small non-zero targets down to the internal `10 W` target delta so it can erase the remaining residual instead of waiting for the global `60 W` command deadband. This applies to available discharge and charge targets, even when the battery is currently idle. When the target entity exposes a positive minimum above that small target, the blueprint clamps the written value to that entity minimum.
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
