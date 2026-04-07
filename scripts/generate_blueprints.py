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
          filter:
            - domain: sensor
              device_class: battery
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
      default: 0
      selector:
        number:
          min: 0
          max: 300
          step: 5
          unit_of_measurement: s
          mode: slider
    battery___SLOT___target_power_entity:
      name: "[[input.battery.target_power_entity.name]]"
      description: "[[input.battery.target_power_entity.description]]"
      default: ""
      selector:
        entity:
          filter:
            - domain: number
            - domain: input_number
    battery___SLOT___discharge_actions:
      name: "[[input.battery.discharge_actions.name]]"
      description: "[[input.battery.discharge_actions.description]]"
      default: []
      selector:
        action: {}
    battery___SLOT___charge_actions:
      name: "[[input.battery.charge_actions.name]]"
      description: "[[input.battery.charge_actions.description]]"
      default: []
      selector:
        action: {}
""".strip()


SLOT_BINDING_TEMPLATE = """
battery___SLOT___soc_sensor: !input battery___SLOT___soc_sensor
battery___SLOT___max_discharge_w: !input battery___SLOT___max_discharge_w
battery___SLOT___max_charge_w: !input battery___SLOT___max_charge_w
battery___SLOT___priority_discharge: !input battery___SLOT___priority_discharge
battery___SLOT___cooldown_seconds: !input battery___SLOT___cooldown_seconds
battery___SLOT___target_power_entity: !input battery___SLOT___target_power_entity
battery___SLOT___discharge_actions: !input battery___SLOT___discharge_actions
battery___SLOT___charge_actions: !input battery___SLOT___charge_actions
""".strip()


SLOT_STATE_TEMPLATE = """
slot___SLOT___used: "{{ battery___SLOT___soc_sensor != '' }}"
slot___SLOT___soc: "{{ states(battery___SLOT___soc_sensor) | float(0) if slot___SLOT___used else 0 }}"
slot___SLOT___actual_power: "0"
slot___SLOT___target_entity_configured: "{{ battery___SLOT___target_power_entity != '' }}"
slot___SLOT___target_power_state: >-
  {% if slot___SLOT___target_entity_configured %}
    {{ states(battery___SLOT___target_power_entity) }}
  {% else %}
    0
  {% endif %}
slot___SLOT___target_last_changed_ts: >-
  {% if slot___SLOT___target_entity_configured %}
    {% set target_state = states[battery___SLOT___target_power_entity] %}
    {{ as_timestamp(target_state.last_changed, 0) if target_state is not none else 0 }}
  {% else %}
    0
  {% endif %}
slot___SLOT___current_target_w: >-
  {% if slot___SLOT___target_power_state in ['unknown', 'unavailable', 'none', ''] %}
    0
  {% else %}
    {{ slot___SLOT___target_power_state | float(0) }}
  {% endif %}
slot___SLOT___current_target_sign: >-
  {% if slot___SLOT___current_target_w | float(0) > 0 %}
    1
  {% elif slot___SLOT___current_target_w | float(0) < 0 %}
    -1
  {% else %}
    0
  {% endif %}
slot___SLOT___has_discharge_actions: "{{ battery___SLOT___discharge_actions | count > 0 }}"
slot___SLOT___has_charge_actions: "{{ battery___SLOT___charge_actions | count > 0 }}"
slot___SLOT___can_discharge: "{{ slot___SLOT___used and slot___SLOT___target_entity_configured and battery___SLOT___max_discharge_w | float(0) > 0 }}"
slot___SLOT___can_charge: "{{ slot___SLOT___used and slot___SLOT___target_entity_configured and battery___SLOT___max_charge_w | float(0) > 0 }}"
""".strip()


SLOT_VALIDATION_TEMPLATE = """
{% if slot___SLOT___used %}
  {% set has_target_entity = slot___SLOT___target_entity_configured | bool %}
  {% set discharge_power_enabled = battery___SLOT___max_discharge_w | float(0) > 0 %}
  {% set charge_power_enabled = battery___SLOT___max_charge_w | float(0) > 0 %}
  {% if not has_target_entity %}
    {% set error_text -%}
      [[slot.__SLOT__]] [[validation.no_target_entity.suffix]]
    {%- endset %}
    {% set ns.errors = ns.errors + [error_text | trim] %}
  {% elif not (discharge_power_enabled or charge_power_enabled) %}
    {% set error_text -%}
      [[slot.__SLOT__]] [[validation.no_power.suffix]]
    {%- endset %}
    {% set ns.errors = ns.errors + [error_text | trim] %}
  {% endif %}
{% endif %}
""".strip()


SLOT_BATTERIES_TEMPLATE = """
{% if slot___SLOT___used %}
  {% set current_target = slot___SLOT___current_target_w | float(0) %}
  {% set ns.items = ns.items + [{
    'slot': __SLOT__,
    'soc': slot___SLOT___soc | float(0),
    'priority': battery___SLOT___priority_discharge | bool,
    'max_discharge': battery___SLOT___max_discharge_w | float(0),
    'max_charge': battery___SLOT___max_charge_w | float(0),
    'can_discharge': slot___SLOT___can_discharge | bool,
    'can_charge': slot___SLOT___can_charge | bool,
    'current_discharge': [current_target, 0] | max,
    'current_charge': [0 - current_target, 0] | max,
    'discharge_locked': slot___SLOT___can_discharge and current_target > 0 and not (discharge_cooldown_ok___SLOT__ | bool),
    'charge_locked': slot___SLOT___can_charge and current_target < 0 and not (charge_cooldown_ok___SLOT__ | bool)
  }] %}
{% endif %}
""".strip()


SLOT_COOLDOWN_TEMPLATE = """
discharge_cooldown_ok___SLOT__: >-
  {% if not slot___SLOT___can_discharge %}
    false
  {% elif battery___SLOT___cooldown_seconds | float(0) <= 0 %}
    true
  {% else %}
    {{ slot___SLOT___target_last_changed_ts == 0 or as_timestamp(now()) - slot___SLOT___target_last_changed_ts >= battery___SLOT___cooldown_seconds | float(0) }}
  {% endif %}
charge_cooldown_ok___SLOT__: >-
  {% if not slot___SLOT___can_charge %}
    false
  {% elif battery___SLOT___cooldown_seconds | float(0) <= 0 %}
    true
  {% else %}
    {{ slot___SLOT___target_last_changed_ts == 0 or as_timestamp(now()) - slot___SLOT___target_last_changed_ts >= battery___SLOT___cooldown_seconds | float(0) }}
  {% endif %}
""".strip()


SLOT_COMMAND_TEMPLATE = """
discharge_active___SLOT__: "{{ operating_mode == 'discharge' and discharge_target___SLOT__ >= command_deadband_w }}"
charge_active___SLOT__: "{{ operating_mode == 'charge' and charge_target___SLOT__ >= command_deadband_w }}"
signed_target___SLOT__: >-
  {% if discharge_active___SLOT__ %}
    {{ discharge_target___SLOT__ | float(0) }}
  {% elif charge_active___SLOT__ %}
    {{ 0 - (charge_target___SLOT__ | float(0)) }}
  {% else %}
    0
  {% endif %}
desired_target_sign___SLOT__: >-
  {% if signed_target___SLOT__ | float(0) > 0 %}
    1
  {% elif signed_target___SLOT__ | float(0) < 0 %}
    -1
  {% else %}
    0
  {% endif %}
should_write_target_power___SLOT__: >-
  {% if not slot___SLOT___target_entity_configured %}
    false
  {% elif operating_mode == 'blocked' %}
    {{ desired_target_sign___SLOT__ | int(0) == 0
       and desired_target_sign___SLOT__ | int(0) != slot___SLOT___current_target_sign | int(0)
       and blocking_trigger_entered_blocked }}
  {% elif desired_target_sign___SLOT__ | int(0) != slot___SLOT___current_target_sign | int(0) %}
    true
  {% elif signed_target___SLOT__ | float(0) > 0 %}
    {{ discharge_cooldown_ok___SLOT__ }}
  {% elif signed_target___SLOT__ | float(0) < 0 %}
    {{ charge_cooldown_ok___SLOT__ }}
  {% else %}
    false
  {% endif %}
should_run_discharge_actions___SLOT__: >-
  {% if not slot___SLOT___has_discharge_actions or signed_target___SLOT__ | float(0) <= 0 %}
    false
  {% elif slot___SLOT___current_target_sign | int(0) != 1 %}
    true
  {% else %}
    {{ discharge_cooldown_ok___SLOT__ }}
  {% endif %}
should_run_charge_actions___SLOT__: >-
  {% if not slot___SLOT___has_charge_actions or signed_target___SLOT__ | float(0) >= 0 %}
    false
  {% elif slot___SLOT___current_target_sign | int(0) != -1 %}
    true
  {% else %}
    {{ charge_cooldown_ok___SLOT__ }}
  {% endif %}
""".strip()


SLOT_ACTION_TEMPLATE = """
- alias: "[[slot.__SLOT__]]: [[trace.write_target_suffix]]"
  choose:
    - alias: "[[slot.__SLOT__]]: [[trace.target_update_branch_suffix]]"
      conditions:
        - condition: template
          value_template: "{{ should_write_target_power___SLOT__ }}"
        - condition: template
          value_template: >-
            {% set blockers = expand(blocking_entities) %}
            {% set blockers_clear = blockers | selectattr('state', 'eq', 'off') | list | count == blockers | count %}
            {% set sensor_state = states(house_power_sensor) %}
            {% set sensor_valid = sensor_state not in ['unknown', 'unavailable', 'none', ''] %}
            {% set zero_allowed = signed_target___SLOT__ | float(0) == 0 and (operating_mode != 'blocked' or blocking_trigger_entered_blocked) %}
            {{ zero_allowed or (blockers_clear and sensor_valid) }}
      sequence:
        - alias: "[[slot.__SLOT__]]: [[trace.prepare_target_context_suffix]]"
          variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_power_w: "{{ signed_target___SLOT__ }}"
            target_discharge_w: "{{ discharge_target___SLOT__ }}"
            target_charge_w: "{{ charge_target___SLOT__ }}"
        - alias: "[[slot.__SLOT__]]: [[trace.select_target_service_suffix]]"
          choose:
            - conditions:
                - condition: template
                  value_template: "{{ battery___SLOT___target_power_entity.startswith('number.') }}"
              sequence:
                - alias: "[[slot.__SLOT__]]: [[trace.write_number_target_suffix]]"
                  action: number.set_value
                  target:
                    entity_id: "{{ battery___SLOT___target_power_entity }}"
                  data:
                    value: "{{ target_power_w | round(0) | int(0) }}"
            - conditions:
                - condition: template
                  value_template: "{{ battery___SLOT___target_power_entity.startswith('input_number.') }}"
              sequence:
                - alias: "[[slot.__SLOT__]]: [[trace.write_input_number_target_suffix]]"
                  action: input_number.set_value
                  target:
                    entity_id: "{{ battery___SLOT___target_power_entity }}"
                  data:
                    value: "{{ target_power_w | round(0) | int(0) }}"
- alias: "[[slot.__SLOT__]]: [[trace.run_discharge_actions_suffix]]"
  choose:
    - alias: "[[slot.__SLOT__]]: [[trace.discharge_actions_branch_suffix]]"
      conditions:
        - condition: template
          value_template: "{{ should_run_discharge_actions___SLOT__ }}"
        - condition: template
          value_template: >-
            {% set blockers = expand(blocking_entities) %}
            {% set blockers_clear = blockers | selectattr('state', 'eq', 'off') | list | count == blockers | count %}
            {% set sensor_state = states(house_power_sensor) %}
            {{ blockers_clear and sensor_state not in ['unknown', 'unavailable', 'none', ''] }}
      sequence:
        - alias: "[[slot.__SLOT__]]: [[trace.prepare_discharge_context_suffix]]"
          variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_power_w: "{{ signed_target___SLOT__ }}"
            target_discharge_w: "{{ discharge_target___SLOT__ }}"
            target_charge_w: "{{ charge_target___SLOT__ }}"
        - alias: "[[slot.__SLOT__]]: [[trace.execute_discharge_actions_suffix]]"
          choose: []
          default: !input battery___SLOT___discharge_actions
- alias: "[[slot.__SLOT__]]: [[trace.run_charge_actions_suffix]]"
  choose:
    - alias: "[[slot.__SLOT__]]: [[trace.charge_actions_branch_suffix]]"
      conditions:
        - condition: template
          value_template: "{{ should_run_charge_actions___SLOT__ }}"
        - condition: template
          value_template: >-
            {% set blockers = expand(blocking_entities) %}
            {% set blockers_clear = blockers | selectattr('state', 'eq', 'off') | list | count == blockers | count %}
            {% set sensor_state = states(house_power_sensor) %}
            {{ blockers_clear and sensor_state not in ['unknown', 'unavailable', 'none', ''] }}
      sequence:
        - alias: "[[slot.__SLOT__]]: [[trace.prepare_charge_context_suffix]]"
          variables:
            battery_slot: __SLOT__
            battery_soc: "{{ slot___SLOT___soc }}"
            battery_actual_power_w: "{{ slot___SLOT___actual_power }}"
            house_power_w: "{{ house_power_w }}"
            import_need_w: "{{ import_need_w }}"
            export_surplus_w: "{{ export_surplus_w }}"
            target_power_w: "{{ signed_target___SLOT__ }}"
            target_discharge_w: "{{ discharge_target___SLOT__ }}"
            target_charge_w: "{{ charge_target___SLOT__ }}"
        - alias: "[[slot.__SLOT__]]: [[trace.execute_charge_actions_suffix]]"
          choose: []
          default: !input battery___SLOT___charge_actions
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
                f'discharge_capable_count: "{{{{ {discharge_count} }}}}"',
                f'charge_capable_count: "{{{{ {charge_count} }}}}"',
                f'near_full_exists: "{{{{ {near_full_expr} }}}}"',
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
