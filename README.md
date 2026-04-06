# home-battery-blueprint

Localized Home Assistant blueprint project for steering up to four batteries from a single house power sensor. The blueprint focuses on discharge, can absorb real export through opportunistic charging, and drives each battery only through custom actions. Each battery is grouped in its own collapsed section by default to keep the form compact.

This blueprint is intentionally generic. It does not try to normalize brand-specific APIs. Instead, each battery slot is driven by:

- custom actions for discharge and/or charge
- optional stop actions to force a return to neutral when the operating mode changes or the blueprint is blocked
- helper entities or vendor services hidden behind those actions when an integration needs an intermediate control surface

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fhome-battery-blueprint%2Fgh-pages%2Fen%2Fhome_battery_manager.yaml)

Raw import URL:

`https://raw.githubusercontent.com/nicolinuxfr/home-battery-blueprint/gh-pages/en/home_battery_manager.yaml`

## Configuration

- `House power sensor`: the main sensor used by the allocator. It must use `import > 0` and `export < 0`.
- `Blocking entities`: optional list of `binary_sensor` or `input_boolean` entities. The blueprint runs only if every selected entity is `off`. If one becomes `on`, `unknown`, or `unavailable`, all managed batteries are returned to neutral and all stop actions are executed.

For each battery slot:

- `State of charge sensor`: leaving it empty disables the slot.
- `Maximum discharge power` and `Maximum charge power`: manual limits used by the allocator.
- `Priority on discharge`: prioritized batteries discharge first; opportunistic charging prefers non-priority batteries first.
- `Command cooldown`: per-battery anti-spam delay for `set` actions only. Set it to `0` to disable it.
- `Set/Stop discharge actions` and `Set/Stop charge actions`: optional custom actions with runtime variables such as `battery_slot`, `battery_soc`, `target_discharge_w`, `target_charge_w`, `house_power_w` and `export_surplus_w`.

Zendure example:

- create a signed helper such as `input_number.zendure_virtual_p1`
- point the Zendure integration `p1meter` option to that helper
- in `Set discharge actions`, write the positive `target_discharge_w` into the helper
- in `Set charge actions`, write the negative `target_charge_w` into the helper
- in both stop actions, write `0`

## How It Works

- The blueprint chooses one exclusive operating mode per run: `discharge`, `charge`, or `neutral`.
- During discharge it allocates `max(house_power, 0)` across batteries, prioritizing flagged batteries first and then sorting by highest state of charge.
- During opportunistic charging it looks for real export, requires at least one battery at `99%` or above, and then fills charge-capable batteries from the lowest state of charge upward, avoiding discharge-priority batteries until needed.
- A fixed internal `50 W` deadband filters tiny command changes and avoids pointless writes or action spam. This replaces the previous user-facing discharge margin and minimum delta knobs.
- Safety comes first: entering charge stops every managed discharge path first, and entering discharge stops every managed charge path first. The blueprint never intentionally charges and discharges managed batteries at the same time.
- Stop actions exist to force a neutral state when the mode changes, when a blocking entity becomes active, or when the house power sensor becomes invalid. This prevents an action-based integration from keeping a stale previous command alive.
- The cooldown only throttles `set` actions. `stop` actions ignore it on purpose, so a battery can always be forced back to neutral immediately.

## Known Limitations

- The blueprint does not create a moving-average helper. If you want a smoothed house signal, provide an already filtered sensor as input.
- For action-only batteries, stop actions should be idempotent because the blueprint may need to repeat them for safety.
- The blueprint metadata and documentation point to `nicolinuxfr/home-battery-blueprint`.
