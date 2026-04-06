# solar-battery-blueprint

Localized Home Assistant blueprint project for steering up to four batteries from a single house power sensor. The blueprint focuses on discharge, can absorb real export through opportunistic charging, and mixes direct `number` entities with optional custom actions per battery.

This blueprint is intentionally generic. It does not try to normalize brand-specific APIs. Instead, each battery slot can be driven by:

- direct writable `number` entities for discharge and/or charge
- custom actions for discharge and/or charge
- both at the same time if a battery needs a direct setpoint plus extra brand-specific steps

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fsolar-battery-blueprint%2Fgh-pages%2Fen%2Funiversal_home_battery_power_manager.yaml)

Raw import URL:

`https://raw.githubusercontent.com/nicolinuxfr/solar-battery-blueprint/gh-pages/en/universal_home_battery_power_manager.yaml`

## Configuration

- `House power sensor`: the main sensor used by the allocator. It must use `import > 0` and `export < 0`.
- `Discharge margin`: watts subtracted from house demand before the blueprint starts discharging.
- `Global control gate`: when this entity is `off`, all managed batteries are returned to neutral and all stop actions are executed.
- `Minimum command delta`: ignores tiny target changes.

For each battery slot:

- `State of charge sensor`: leaving it empty disables the slot.
- `Actual power sensor`: optional signed power sensor used as a safety hint.
- `Maximum discharge power` and `Maximum charge power`: manual limits used by the allocator.
- `Priority on discharge`: prioritized batteries discharge first; opportunistic charging prefers non-priority batteries first.
- `Command cooldown`: per-battery anti-spam delay.
- `Direct discharge number` and `Direct charge number`: optional direct control entities.
- `Set/Stop discharge actions` and `Set/Stop charge actions`: optional custom actions with runtime variables such as `battery_slot`, `battery_soc`, `target_discharge_w`, `target_charge_w`, `house_power_w` and `export_surplus_w`.

## How It Works

- The blueprint chooses one exclusive operating mode per run: `discharge`, `charge`, or `neutral`.
- During discharge it allocates `max(house_power - margin, 0)` across batteries, prioritizing flagged batteries first and then sorting by highest state of charge.
- During opportunistic charging it looks for real export, requires at least one battery at `99%` or above, and then fills charge-capable batteries from the lowest state of charge upward, avoiding discharge-priority batteries until needed.
- Safety comes first: entering charge stops every managed discharge path first, and entering discharge stops every managed charge path first. The blueprint never intentionally charges and discharges managed batteries at the same time.

## Known Limitations

- The blueprint does not create a moving-average helper. If you want a smoothed house signal, provide an already filtered sensor as input.
- A single bidirectional direct command entity is not supported as a direct field pair. Use custom actions for that case.
- For action-only batteries, stop actions should be idempotent because the blueprint may need to repeat them for safety.
- The optional actual power sensor works best when it is signed: positive for discharge, negative for charge.
- The blueprint metadata and documentation point to `nicolinuxfr/solar-battery-blueprint`.
