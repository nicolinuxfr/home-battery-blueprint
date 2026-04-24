#!/usr/bin/env python3
from __future__ import annotations


COMMAND_DEADBAND_W = 60
MINIMUM_TARGET_DELTA_W = 10


def locked_discharge_reduction_pending(slots: list[dict[str, float | bool]]) -> bool:
    for slot in slots:
        current = float(slot["current_target_w"])
        target = float(slot["discharge_target_w"])
        cooldown_ok = bool(slot["discharge_cooldown_ok"])
        if (
            current > 0
            and target >= COMMAND_DEADBAND_W
            and target < current - MINIMUM_TARGET_DELTA_W
            and not cooldown_ok
        ):
            return True
    return False


def discharge_increase_blocked_by_locked_reduction(
    *,
    current_target_w: float,
    signed_target_w: float,
    locked_reduction_pending: bool,
    export_guard_active: bool,
) -> bool:
    return (
        locked_reduction_pending
        and signed_target_w > current_target_w
        and signed_target_w > 0
        and not export_guard_active
    )


def test_priority_increase_waits_for_locked_reduction() -> None:
    # Captured from home_battery_blueprint_runs (8).jsonl at 2026-04-24 14:42:35.
    # Battery 1 wanted to jump from 80 W to 1200 W while battery 3 needed to
    # drop from 2091 W to 1013 W but was still inside its response cooldown.
    slots = [
        {"current_target_w": 80, "discharge_target_w": 1200, "discharge_cooldown_ok": True},
        {"current_target_w": 800, "discharge_target_w": 800, "discharge_cooldown_ok": True},
        {"current_target_w": 2091, "discharge_target_w": 1013, "discharge_cooldown_ok": False},
    ]
    pending = locked_discharge_reduction_pending(slots)
    assert pending
    assert discharge_increase_blocked_by_locked_reduction(
        current_target_w=80,
        signed_target_w=1200,
        locked_reduction_pending=pending,
        export_guard_active=False,
    )


def test_export_guard_still_allows_corrections() -> None:
    assert not discharge_increase_blocked_by_locked_reduction(
        current_target_w=80,
        signed_target_w=1200,
        locked_reduction_pending=True,
        export_guard_active=True,
    )


def main() -> int:
    test_priority_increase_waits_for_locked_reduction()
    test_export_guard_still_allows_corrections()
    print("Regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
