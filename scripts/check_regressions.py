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
    house_power_w: float,
    locked_reduction_pending: bool,
    export_guard_active: bool,
) -> bool:
    return (
        locked_reduction_pending
        and signed_target_w > current_target_w
        and signed_target_w > 0
        and (signed_target_w - current_target_w) > max(house_power_w, 0)
        and not export_guard_active
    )


def priority_assist_gap(
    *,
    desired_allocation_w: float,
    current_discharge_w: float,
    actual_discharge_w: float,
    target_age_s: float,
    response_grace_s: float,
    discharge_locked: bool,
    priority: bool,
    actual_power_usable: bool,
) -> float:
    ramping_now = desired_allocation_w > current_discharge_w
    still_ramping = discharge_locked and target_age_s < response_grace_s
    if (
        priority
        and actual_power_usable
        and desired_allocation_w > actual_discharge_w
        and (ramping_now or still_ramping)
    ):
        return max(desired_allocation_w - actual_discharge_w, 0)
    return 0


def export_trimmed_allocation(
    *,
    current_allocation_w: float,
    actual_discharge_w: float,
    trim_remaining_w: float,
    actual_power_fresh: bool,
    target_age_s: float,
    response_grace_s: float,
) -> tuple[float, float]:
    if (
        actual_power_fresh
        and target_age_s < response_grace_s
        and actual_discharge_w > current_allocation_w + COMMAND_DEADBAND_W
    ):
        pending_actual_drop = min(actual_discharge_w - current_allocation_w, trim_remaining_w)
        trim_remaining_w = max(trim_remaining_w - pending_actual_drop, 0)
    trim_allocation = min(current_allocation_w, trim_remaining_w)
    return current_allocation_w - trim_allocation, max(trim_remaining_w - trim_allocation, 0)


def discharge_delivery_stalled(
    *,
    current_target_w: float,
    actual_discharge_w: float,
    target_age_s: float,
    response_grace_s: float,
    actual_power_stale: bool,
    actual_power_usable: bool,
) -> bool:
    if actual_power_stale:
        return True
    if current_target_w <= 0 or target_age_s < response_grace_s:
        return False
    if actual_power_usable:
        return actual_discharge_w <= 50 and (current_target_w - actual_discharge_w) > 50
    return False


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
        house_power_w=60.1,
        locked_reduction_pending=pending,
        export_guard_active=False,
    )


def test_real_import_allows_matching_increase() -> None:
    assert not discharge_increase_blocked_by_locked_reduction(
        current_target_w=0,
        signed_target_w=645,
        house_power_w=645,
        locked_reduction_pending=True,
        export_guard_active=False,
    )


def test_non_fresh_usable_priority_telemetry_still_assists() -> None:
    assert priority_assist_gap(
        desired_allocation_w=1200,
        current_discharge_w=920,
        actual_discharge_w=540,
        target_age_s=20,
        response_grace_s=60,
        discharge_locked=True,
        priority=True,
        actual_power_usable=True,
    ) == 660


def test_stale_priority_telemetry_does_not_assist() -> None:
    assert priority_assist_gap(
        desired_allocation_w=1200,
        current_discharge_w=920,
        actual_discharge_w=540,
        target_age_s=20,
        response_grace_s=60,
        discharge_locked=True,
        priority=True,
        actual_power_usable=False,
    ) == 0


def test_export_trim_credits_pending_actual_drop() -> None:
    allocation, remaining = export_trimmed_allocation(
        current_allocation_w=1827.1,
        actual_discharge_w=3016,
        trim_remaining_w=1108.9,
        actual_power_fresh=True,
        target_age_s=19.1,
        response_grace_s=20,
    )
    assert round(allocation, 1) == 1827.1
    assert remaining == 0


def test_export_trim_still_cuts_when_pending_drop_is_not_fresh() -> None:
    allocation, remaining = export_trimmed_allocation(
        current_allocation_w=1827.1,
        actual_discharge_w=3016,
        trim_remaining_w=1108.9,
        actual_power_fresh=False,
        target_age_s=19.1,
        response_grace_s=20,
    )
    assert round(allocation, 1) == 718.2
    assert remaining == 0


def test_export_trim_still_cuts_after_response_window() -> None:
    allocation, remaining = export_trimmed_allocation(
        current_allocation_w=1827.1,
        actual_discharge_w=3016,
        trim_remaining_w=1108.9,
        actual_power_fresh=True,
        target_age_s=21,
        response_grace_s=20,
    )
    assert round(allocation, 1) == 718.2
    assert remaining == 0


def test_export_guard_still_allows_corrections() -> None:
    assert not discharge_increase_blocked_by_locked_reduction(
        current_target_w=80,
        signed_target_w=1200,
        house_power_w=60.1,
        locked_reduction_pending=True,
        export_guard_active=True,
    )


def test_stale_actual_power_blocks_new_discharge_allocation() -> None:
    assert discharge_delivery_stalled(
        current_target_w=0,
        actual_discharge_w=0,
        target_age_s=360,
        response_grace_s=60,
        actual_power_stale=True,
        actual_power_usable=False,
    )


def test_zero_target_without_stale_telemetry_remains_available() -> None:
    assert not discharge_delivery_stalled(
        current_target_w=0,
        actual_discharge_w=0,
        target_age_s=360,
        response_grace_s=60,
        actual_power_stale=False,
        actual_power_usable=False,
    )


def main() -> int:
    test_priority_increase_waits_for_locked_reduction()
    test_real_import_allows_matching_increase()
    test_non_fresh_usable_priority_telemetry_still_assists()
    test_stale_priority_telemetry_does_not_assist()
    test_export_trim_credits_pending_actual_drop()
    test_export_trim_still_cuts_when_pending_drop_is_not_fresh()
    test_export_trim_still_cuts_after_response_window()
    test_export_guard_still_allows_corrections()
    test_stale_actual_power_blocks_new_discharge_allocation()
    test_zero_target_without_stale_telemetry_remains_available()
    print("Regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
