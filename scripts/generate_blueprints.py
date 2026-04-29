#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"\[\[([a-zA-Z0-9_.-]+)\]\]")
SLOTS = range(1, 5)
INCLUDE_DIR = Path(__file__).resolve().parent.parent / "includes"


def load_include(filename: str) -> str:
    path = INCLUDE_DIR / filename
    if not path.exists():
        raise SystemExit(f"Include file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


SLOT_INPUT_TEMPLATE = load_include("slot_inputs.yaml")


SLOT_BINDING_TEMPLATE = load_include("slot_bindings.yaml")


SLOT_STATE_TEMPLATE = load_include("slot_state_vars.yaml")


SLOT_VALIDATION_TEMPLATE = load_include("slot_validation_lines.yaml")


SLOT_BATTERIES_TEMPLATE = load_include("batteries_json_lines.yaml")


SLOT_COOLDOWN_TEMPLATE = load_include("cooldown_vars.yaml")


SLOT_COMMAND_TEMPLATE = load_include("command_vars.yaml")


SLOT_NIGHT_CHARGE_ACTION_TEMPLATE = load_include("slot_night_charge_actions.yaml")


SLOT_ACTION_TEMPLATE = load_include("slot_actions.yaml")


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
            ]
        ),
        "generated.cooldown_vars": join_blocks(
            [slotize(SLOT_COOLDOWN_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.command_vars": join_blocks(
            [slotize(SLOT_COMMAND_TEMPLATE, slot) for slot in SLOTS]
        ),
        "generated.night_charge_actions": join_blocks(
            [slotize(SLOT_NIGHT_CHARGE_ACTION_TEMPLATE, slot) for slot in SLOTS]
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
