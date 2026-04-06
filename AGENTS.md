# Instructions

- For any requested blueprint change, always apply the change in `template.yaml`.
- Always update all translation files in parallel when a blueprint text or key is changed.
- Update all README files accordingly.
- Change the version number inside `VERSION` only when asked to. You may suggest a version bump after significant changes.
- Respect this CalVer format: `YYYY.MM.x`
- First release of the month: `YYYY.MM`
- Subsequent releases in the same month: `YYYY.MM.2`, `YYYY.MM.3`, etc.
- If the version changes, add a matching entry to `CHANGELOG.md` and let the user review it.
- Keep the blueprint vendor-agnostic by default. Do not hard-code brand-specific assumptions when the same behavior can be expressed through generic entities or optional custom actions.
