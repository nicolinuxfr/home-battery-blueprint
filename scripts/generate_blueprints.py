#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"\[\[([a-zA-Z0-9_.-]+)\]\]")
SLOTS = range(1, 5)


SLOT_INPUT_TEMPLATE = """
battery___SLOT___section:
  name: "[[slot.__SLOT__]]"
  icon: mdi:battery
  collapsed: true
  input:
    battery___SLOT___soc_sensor:
      name: "[[input.battery.soc_sensor.name]]"
      description: "[[input.battery.soc_sensor.description]]"
      default: ""
      selector:
        entity:
          domain: sensor
    battery___SLOT___actual_power_sensor:
      name: "[[input.battery.actual_power_sensor.name]]"
      description: "[[input.battery.actual_power_sensor.description]]"
      default: ""
      selector:
        entity:
          domain: sensor
    battery___SLOT___max_discharge_w:
      name: "[[input.battery.max_discharge_w.name]]"
      description: "[[input.battery.max_discharge_w.description]]"
      default: 0
      selector:
        number:
          min: 0
          max: 5000
          step: 10
          unit_of_measurement: W
          mode: box
    battery___SLOT___max_charge_w:
      name: "[[input.battery.max_charge_w.name]]"
      description: "[[input.battery.max_charge_w.description]]"
      default: 0
      selector:
        number:
          min: 0
          max: 5000
          step: 10
          unit_of_measurement: W
          mode: box
    battery___SLOT___priority_discharge:
      name: "[[input.battery.priority_discharge.name]]"
      description: "[[input.battery.priority_discharge.description]]"
      default: false
      selector:
        boolean: {}
    battery___SLOT___cooldown_seconds:
      name: "[[input.battery.cooldown_seconds.name]]"
      description: "[[input.battery.cooldown_seconds.description]]"
      default: 60
      selector:
        number:
          min: 5
          max: 300
          step: 5
          unit_of_measurement: s
          mode: slider
    battery___SLOT___discharge_target_number:
      name: "[[input.battery.discharge_target_number.name]]"
      description: "[[input.battery.discharge_target_number.description]]"
      default: ""
      selector:
        entity:
          domain: number
    battery___SLOT___charge_target_number:
      name: "[[input.battery.charge_target_number.name]]"
      description: "[[input.battery.charge_target_number.description]]"
      default: ""
      selector:
        entity:
          domain: number
    battery___SLOT___set_discharge_actions:
      name: "[[input.battery.set_discharge_actions.name]]"
      description: "[[input.battery.set_discharge_actions.description]]"
      default: []
      selector:
        action: {}
    battery___SLOT___stop_discharge_actions:
      name: "[[input.battery.stop_discharge_actions.name]]"
      description: "[[input.battery.stop_discharge_actions.description]]"
      default: []
      selector:
        action: {}
    battery___SLOT___set_charge_actions:
      name: "[[input.battery.set_charge_actions.name]]"
      description: "[[input.battery.set_charge_actions.description]]"
      default: []
      selector:
        action: {}
    battery___SLOT___stop_charge_actions:
      name: "[[input.battery.stop_charge_actions.name]]"
      description: "[[input.battery.stop_charge_actions.description]]"
      default: []
      selector:
        action: {}
""".strip()


SLOT_BINDING_TEMPLATE = """
battery___SLOT___soc_sensor: !input battery___SLOT___soc_sensor
battery___SLOT___actual_power_sensor: !input battery___SLOT___actual_power_sensor
battery___SLOT___max_discharge_w: !input battery___SLOT___max_discharge_w
battery___SLOT___max_charge_w: !input battery___SLOT___max_charge_w
battery___SLOT___priority_discharge: !input battery___SLOT___priority_discharge
battery___SLOT___cooldown_seconds: !input battery___SLOT___cooldown_seconds
battery___SLOT___discharge_target_number: !input battery___SLOT___discharge_target_number
battery___SLOT___charge_target_number: !input battery___SLOT___charge_target_number
battery___SLOT___set_discharge_actions: !input battery___SLOT___set_discharge_actions
battery___SLOT___stop_discharge_actions: !input battery___SLOT___stop_discharge_actions
battery___SLOT___set_charge_actions: !input battery___SLOT___set_charge_actions
battery___SLOT___stop_charge_actions: !input battery___SLOT___stop_charge_actions
""".strip()


SLOT_STATE_TEMPLATE = """
slot___SLOT___used: "{{ battery___SLOT___soc_sensor != '' }}"
slot___SLOT___soc: "{{ states(battery___SLOT___soc_sensor) | float(0) if slot___SLOT___used else 0 }}"
slot___SLOT___actual_power: "{{ states(battery___SLOT___actual_power_sensor) | float(0) if battery___SLOT___actual_power_sensor != '' else 0 }}"
slot___SLOT___discharge_direct: "{{ battery___SLOT___discharge_target_number != '' }}"
slot___SLOT___charge_direct: "{{ battery___SLOT___charge_target_number != '' }}"
slot___SLOT___has_discharge_actions: "{{ battery___SLOT___set_discharge_actions | count > 0 }}"
slot___SLOT___has_stop_discharge_actions: "{{ battery___SLOT___stop_discharge_actions | count > 0 }}"
slot___SLOT___has_charge_actions: "{{ battery___SLOT___set_charge_actions | count > 0 }}"
slot___SLOT___has_stop_charge_actions: "{{ battery___SLOT___stop_charge_actions | count > 0 }}"
slot___SLOT___can_discharge: "{{ slot___SLOT___used and battery___SLOT___max_discharge_w | float(0) > 0 and (slot___SLOT___discharge_direct or slot___SLOT___has_discharge_actions) }}"
slot___SLOT___can_charge: "{{ slot___SLOT___used and battery___SLOT___max_charge_w | float(0) > 0 and (slot___SLOT___charge_direct or slot___SLOT___has_charge_actions) }}"
current_discharge_number___SLOT__: "{{ states(battery___SLOT___discharge_target_number) | float(0) if slot___SLOT___discharge_direct else 0 }}"
current_charge_number___SLOT__: "{{ states(battery___SLOT___charge_target_number) | float(0) if slot___SLOT___charge_direct else 0 }}"
""".strip()


SLOT_VALIDATION_TEMPLATE = """
{% if slot___SLOT___used and slot___SLOT___discharge_direct and slot___SLOT___charge_direct and battery___SLOT___discharge_target_number == battery___SLOT___charge_target_number %}
  {% set ns.errors = ns.errors + ['[[slot.__SLOT__]] [[validation.same_direct_number.suffix]]'] %}
{% endif %}
{% if slot___SLOT___used and not (slot___SLOT___can_discharge or slot___SLOT___can_charge) %}
  {% set ns.errors = ns.errors + ['[[slot.__SLOT__]] [[validation.no_interface.suffix]]'] %}
{% endif %}
""".strip()


SLOT_BATTERIES_TEMPLATE = """
{% if slot___SLOT___used %}
  {% set ns.items = ns.items + [{'slot': __SLOT__, 'soc': slot___SLOT___soc | float(0), 'priority': battery___SLOT___priority_discharge | bool, 'max_discharge': battery___SLOT___max_discharge_w | float(0), 'max_charge': battery___SLOT___max_charge_w | float(0), 'can_discharge': slot___SLOT___can_discharge | bool, 'can_charge': slot___SLOT___can_charge | bool}] %}
{% endif %}
""".strip()


SLOT_COOLDOWN_TEMPLATE = """
discharge_cooldown_ok___SLOT__: >-
  {% if not slot___SLOT___can_discharge %}
    false
  {% elif slot___SLOT___discharge_direct %}
    {{ as_timestamp(now()) - as_timestamp(states[battery___SLOT___discharge_target_number].last_changed, 0) >= battery___SLOT___cooldown_seconds | float(0) }}
  {% elif battery___SLOT___actual_power_sensor != '' %}
    {{ as_timestamp(now()) - as_timestamp(states[battery___SLOT___actual_power_sensor].last_changed, 0) >= battery___SLOT___cooldown_seconds | float(0) }}
  {% else %}
    {{ automation_last_triggered_ts == 0 or as_timestamp(now()) - automation_last_triggered_ts >= battery___SLOT___cooldown_seconds | float(0) }}
  {% endif %}
charge_cooldown_ok___SLOT__: >-
  {% if not slot___SLOT___can_charge %}
    false
  {% elif slot___SLOT___charge_direct %}
    {{ as_timestamp(now()) - as_timestamp(states[battery___SLOT___charge_target_number].last_changed, 0) >= battery___SLOT___cooldown_seconds | float(0) }}
  {% elif battery___SLOT___actual_power_sensor != '' %}
    {{ as_timestamp(now()) - as_timestamp(states[battery___SLOT___actual_power_sensor].last_changed, 0) >= battery___SLOT___cooldown_seconds | float(0) }}
  {% else %}
    {{ automation_last_triggered_ts == 0 or as_timestamp(now()) - automation_last_triggered_ts >= battery___SLOT___cooldown_seconds | float(0) }}
  {% endif %}
""".strip()


SLOT_COMMAND_TEMPLATE = """
discharge_active___SLOT__: "{{ operating_mode == 'discharge' and discharge_target___SLOT__ >= command_deadband_w }}"
charge_active___SLOT__: "{{ operating_mode == 'charge' and charge_target___SLOT__ >= command_deadband_w }}"
should_write_discharge_number___SLOT__: "{{ slot___SLOT___discharge_direct and discharge_active___SLOT__ and discharge_cooldown_ok___SLOT__ and (discharge_target___SLOT__ - current_discharge_number___SLOT__) | abs >= command_deadband_w }}"
should_write_charge_number___SLOT__: "{{ slot___SLOT___charge_direct and charge_active___SLOT__ and charge_cooldown_ok___SLOT__ and (charge_target___SLOT__ - current_charge_number___SLOT__) | abs >= command_deadband_w }}"
should_run_discharge_actions___SLOT__: "{{ slot___SLOT___has_discharge_actions and discharge_active___SLOT__ and discharge_cooldown_ok___SLOT__ and (not slot___SLOT___discharge_direct or should_write_discharge_number___SLOT__) }}"
should_run_charge_actions___SLOT__: "{{ slot___SLOT___has_charge_actions and charge_active___SLOT__ and charge_cooldown_ok___SLOT__ and (not slot___SLOT___charge_direct or should_write_charge_number___SLOT__) }}"
should_reset_discharge_number___SLOT__: "{{ slot___SLOT___discharge_direct and not discharge_active___SLOT__ and current_discharge_number___SLOT__ | abs > 0 }}"
should_reset_charge_number___SLOT__: "{{ slot___SLOT___charge_direct and not charge_active___SLOT__ and current_charge_number___SLOT__ | abs > 0 }}"
should_stop_discharge_actions___SLOT__: "{{ slot___SLOT___has_stop_discharge_actions and not discharge_active___SLOT__ and (should_reset_discharge_number___SLOT__ or slot___SLOT___actual_power > command_deadband_w or (not slot___SLOT___discharge_direct and battery___SLOT___actual_power_sensor == '')) }}"
should_stop_charge_actions___SLOT__: "{{ slot___SLOT___has_stop_charge_actions and not charge_active___SLOT__ and (should_reset_charge_number___SLOT__ or slot___SLOT___actual_power < (0 - command_deadband_w) or (not slot___SLOT___charge_direct and battery___SLOT___actual_power_sensor == '')) }}"
""".strip()


SLOT_ACTION_TEMPLATE = """
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_reset_discharge_number___SLOT__ }}"
      sequence:
        - action: number.set_value
          target:
            entity_id: !input battery___SLOT___discharge_target_number
          data:
            value: 0
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_stop_discharge_actions___SLOT__ }}"
      sequence:
        - variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_discharge_w: 0
            target_charge_w: "{{ charge_target___SLOT__ }}"
        - choose: []
          default: !input battery___SLOT___stop_discharge_actions
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_reset_charge_number___SLOT__ }}"
      sequence:
        - action: number.set_value
          target:
            entity_id: !input battery___SLOT___charge_target_number
          data:
            value: 0
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_stop_charge_actions___SLOT__ }}"
      sequence:
        - variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_discharge_w: "{{ discharge_target___SLOT__ }}"
            target_charge_w: 0
        - choose: []
          default: !input battery___SLOT___stop_charge_actions
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_write_discharge_number___SLOT__ }}"
      sequence:
        - action: number.set_value
          target:
            entity_id: !input battery___SLOT___discharge_target_number
          data:
            value: "{{ discharge_target___SLOT__ | round(0) }}"
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_run_discharge_actions___SLOT__ }}"
      sequence:
        - variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_discharge_w: "{{ discharge_target___SLOT__ }}"
            target_charge_w: 0
        - choose: []
          default: !input battery___SLOT___set_discharge_actions
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_write_charge_number___SLOT__ }}"
      sequence:
        - action: number.set_value
          target:
            entity_id: !input battery___SLOT___charge_target_number
          data:
            value: "{{ charge_target___SLOT__ | round(0) }}"
- choose:
    - conditions:
        - condition: template
          value_template: "{{ should_run_charge_actions___SLOT__ }}"
      sequence:
        - variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_discharge_w: 0
            target_charge_w: "{{ charge_target___SLOT__ }}"
        - choose: []
          default: !input battery___SLOT___set_charge_actions
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render localized blueprint YAML files from a template and i18n dictionaries."
    )
    parser.add_argument("--template", default="template.yaml", help="Path to template YAML.")
    parser.add_argument("--i18n-dir", default="languages", help="Directory with <lang>.json files.")
    parser.add_argument("--output-dir", default="dist", help="Output directory for generated files.")
    parser.add_argument(
        "--default-lang",
        default="en",
        help="Fallback language code. Must exist in languages directory.",
    )
    parser.add_argument(
        "--filename",
        default="home_battery_manager.yaml",
        help="Filename used for each generated blueprint.",
    )
    parser.add_argument(
        "--version-file",
        default="VERSION",
        help="Path to plain-text version file injected as [[blueprint.version]].",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"Expected object at top-level in {path}")

    out: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise SystemExit(f"Non-string key in {path}: {key!r}")
        if not isinstance(value, str):
            raise SystemExit(f"Value for key {key!r} in {path} must be a string")
        out[key] = value
    return out


def load_version(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Version file not found: {path}")
    version = path.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit(f"Version file is empty: {path}")
    return version


def build_version_line(template_value: str, version: str, lang: str) -> str:
    try:
        return template_value.format(version=version)
    except KeyError as exc:
        missing = exc.args[0]
        raise SystemExit(
            f"Dictionary '{lang}' has invalid blueprint.version.line placeholder "
            f"'{{{missing}}}'. Use '{{version}}'."
        ) from exc


def render_once(template: str, values: dict[str, str]) -> str:
    errors: list[str] = []

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            errors.append(key)
            return match.group(0)

        value = values[key]
        if "\n" not in value:
            return value

        line_start = template.rfind("\n", 0, match.start()) + 1
        indent = template[line_start:match.start()]
        lines = value.splitlines()
        if not lines:
            return ""
        return lines[0] + "\n" + "\n".join(indent + line for line in lines[1:])

    rendered = TOKEN_RE.sub(repl, template)
    if errors:
        missing = ", ".join(sorted(set(errors)))
        raise SystemExit(f"Missing placeholder values for keys: {missing}")
    return rendered


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for _ in range(10):
        next_rendered = render_once(rendered, values)
        if next_rendered == rendered or not TOKEN_RE.search(next_rendered):
            return next_rendered
        rendered = next_rendered

    unresolved = ", ".join(sorted(set(TOKEN_RE.findall(rendered))))
    raise SystemExit(
        "Unresolved placeholders remain after recursive rendering: "
        + unresolved
    )


def slotize(template: str, slot: int) -> str:
    return template.replace("__SLOT__", str(slot))


def join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block.rstrip() for block in blocks if block).strip()


def build_generated_values() -> dict[str, str]:
    discharge_count = " + ".join(f"slot_{slot}_can_discharge | int(0)" for slot in SLOTS)
    charge_count = " + ".join(f"slot_{slot}_can_charge | int(0)" for slot in SLOTS)
    near_full_expr = " or ".join(
        f"(slot_{slot}_used and slot_{slot}_soc >= 99)" for slot in SLOTS
    )

    return {
        "generated.slot_inputs": join_blocks([slotize(SLOT_INPUT_TEMPLATE, slot) for slot in SLOTS]),
        "generated.slot_bindings": join_blocks(
            [slotize(SLOT_BINDING_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.slot_state_vars": join_blocks(
            [slotize(SLOT_STATE_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.slot_validation_lines": join_blocks(
            [slotize(SLOT_VALIDATION_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.batteries_json_lines": join_blocks(
            [slotize(SLOT_BATTERIES_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.count_vars": "\n".join(
            [
                f'discharge_capable_count: "{{ {discharge_count} }}"',
                f'charge_capable_count: "{{ {charge_count} }}"',
                f'near_full_exists: "{{ {near_full_expr} }}"',
            ]
        ),
        "generated.cooldown_vars": join_blocks(
            [slotize(SLOT_COOLDOWN_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.command_vars": join_blocks(
            [slotize(SLOT_COMMAND_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.slot_actions": join_blocks(
            [slotize(SLOT_ACTION_TEMPLATE, slot) for slot in SLOTS]
        ),
    }


def main() -> int:
    args = parse_args()

    template_path = Path(args.template)
    i18n_dir = Path(args.i18n_dir)
    output_dir = Path(args.output_dir)
    version_file = Path(args.version_file)

    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")
    if not i18n_dir.exists() or not i18n_dir.is_dir():
        raise SystemExit(f"i18n directory not found: {i18n_dir}")

    template = template_path.read_text(encoding="utf-8")
    if not TOKEN_RE.search(template):
        raise SystemExit("No placeholders found in template.")

    version = load_version(version_file)
    computed_values = {
        "blueprint.version": version,
        "blueprint.version.nodots": version.replace(".", ""),
    } | build_generated_values()
    template_keys = set(TOKEN_RE.findall(template))
    for value in computed_values.values():
        template_keys.update(TOKEN_RE.findall(value))
    required_i18n_keys = template_keys - set(computed_values)

    dictionaries: dict[str, dict[str, str]] = {}
    for path in sorted(i18n_dir.glob("*.json")):
        dictionaries[path.stem] = load_json(path)

    if not dictionaries:
        raise SystemExit("No i18n dictionaries found.")

    if args.default_lang not in dictionaries:
        raise SystemExit(
            f"Fallback language '{args.default_lang}' not found in {i18n_dir}."
        )

    default_dict = dictionaries[args.default_lang]
    missing_default = sorted(required_i18n_keys - set(default_dict))
    if missing_default:
        raise SystemExit(
            "Fallback dictionary is missing keys required by template: "
            + ", ".join(missing_default)
        )

    unknown_in_default = sorted(set(default_dict) - required_i18n_keys)
    if unknown_in_default:
        raise SystemExit(
            f"Fallback dictionary has unknown keys not used by template: {', '.join(unknown_in_default)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    for lang, local_dict in dictionaries.items():
        unknown_keys = sorted(set(local_dict) - required_i18n_keys)
        if unknown_keys:
            raise SystemExit(
                f"Dictionary '{lang}' has unknown keys not used by template: {', '.join(unknown_keys)}"
            )

        values = default_dict | local_dict
        version_line = build_version_line(values["blueprint.version.line"], version, lang)
        render_values = computed_values | values | {"blueprint.version.line": version_line}
        rendered = render_template(template, render_values)

        lang_out_dir = output_dir / lang
        lang_out_dir.mkdir(parents=True, exist_ok=True)
        (lang_out_dir / args.filename).write_text(rendered, encoding="utf-8")

    print(
        f"Rendered {len(dictionaries)} language(s) to '{output_dir}'. "
        f"Fallback language: '{args.default_lang}'. "
        f"Version: '{computed_values['blueprint.version']}'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
