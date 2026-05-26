from backend.modules.scheduling import (
    get_staffing_needs, assign_shifts, find_replacement,
    generate_weekly_schedule, set_cell_shifts, move_shift,
    auto_reschedule_day,
)


def test_get_staffing_needs(store):
    count = get_staffing_needs(store, "Monday", "early")
    assert count == 4


def test_get_staffing_needs_missing_returns_zero(store):
    count = get_staffing_needs(store, "Sunday", "early")
    assert count == 0


def test_assign_shifts_basic(store):
    shifts = assign_shifts(store, "2026-05-20", "早班", 4, {})
    assert len(shifts) == 3  # conftest has only 3 staff, can't assign 4
    ids = [s.staff_id for s in shifts]
    assert len(set(ids)) == 3  # no duplicate staff


def test_assign_shifts_fair_rotation(store):
    """Staff with fewer shifts should be preferred."""
    counts = {"s1": 3, "s2": 0, "s3": 0}
    shifts = assign_shifts(store, "2026-05-20", "早班", 1, counts)
    # Should pick someone with 0 shifts, not s1 who already has 3
    assert shifts[0].staff_id != "s1"


def test_assign_shifts_avoids_double(store):
    """Staff already working today should be deprioritized."""
    counts = {}
    daily = {"s1": 1}
    shifts = assign_shifts(store, "2026-05-20", "晚班", 1, counts, daily)
    # s1 already worked morning, so someone else should be picked
    assert shifts[0].staff_id != "s1"


def test_assign_shifts_not_enough_staff(store):
    """If count exceeds active staff, assign everyone."""
    shifts = assign_shifts(store, "2026-05-20", "早班", 10, {})
    assert len(shifts) == 3  # conftest has 3 staff


def test_find_replacement(store):
    shifts = assign_shifts(store, "2026-05-20", "早班", 3, {})
    absentee = shifts[0].staff_id
    candidates = find_replacement(store, absentee, shifts, "2026-05-20")
    assert absentee not in [c.id for c in candidates]


def test_generate_weekly_schedule(store):
    schedule = generate_weekly_schedule(store, "2026-05-18")
    assert schedule.week_start == "2026-05-18"
    assert len(schedule.shifts) > 0
    dates = {s.date for s in schedule.shifts}
    assert len(dates) >= 5


def test_set_cell_shifts(store):
    result = set_cell_shifts(store, "2026-05-20", "早班", ["s1", "s2"])
    assert len(result) == 2
    assert {s.staff_id for s in result} == {"s1", "s2"}


def test_move_shift(store):
    store.save_shifts([])  # clear
    set_cell_shifts(store, "2026-05-20", "早班", ["s1"])
    ok = move_shift(store, "s1", "2026-05-20", "早班", "2026-05-21", "晚班")
    assert ok
    # s1 should now be on 21st evening, not 20th morning
    all_shifts = store.get_shifts("2026-05-18")
    assert not any(s.date == "2026-05-20" and s.period == "早班" and s.staff_id == "s1" for s in all_shifts)
    assert any(s.date == "2026-05-21" and s.period == "晚班" and s.staff_id == "s1" for s in all_shifts)


def test_auto_reschedule_day(store):
    """Auto reschedule replaces all shifts for a staff member on a date."""
    set_cell_shifts(store, "2026-05-20", "早班", ["s1", "s2"])
    set_cell_shifts(store, "2026-05-20", "晚班", ["s1"])
    result = auto_reschedule_day(store, "s1", "2026-05-20")
    assert result["ok"]
    assert len(result["replacements"]) == 2  # morning + evening
    # s1 should no longer be on 2026-05-20
    all_shifts = store.get_shifts("2026-05-18")
    assert not any(s.date == "2026-05-20" and s.staff_id == "s1" for s in all_shifts)
    # s3 should be the replacement (only available staff in conftest: s1 absent, s2 busy)
    periods_replaced = {r["period"] for r in result["replacements"]}
    assert periods_replaced == {"早班", "晚班"}


def test_auto_reschedule_no_shifts(store):
    """Returns error when staff has no shifts on that date."""
    result = auto_reschedule_day(store, "nonexistent", "2026-05-20")
    assert not result["ok"]
