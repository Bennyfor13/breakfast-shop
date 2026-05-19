from backend.data.models import Role
from backend.modules.scheduling import (
    get_staffing_needs, assign_shifts, find_replacement,
    generate_weekly_schedule,
)


def test_get_staffing_needs(store):
    needs = get_staffing_needs(store, "Monday", "early")
    assert needs == {"后厨": 2, "传菜": 1, "收银": 1}


def test_get_staffing_needs_missing_returns_empty(store):
    needs = get_staffing_needs(store, "Sunday", "early")
    assert needs == {}


def test_assign_shifts_basic(store):
    needs = {"后厨": 2, "传菜": 1, "收银": 1}
    shifts = assign_shifts(store, "2026-05-20", "早班", needs, boss_absent=False)
    assert len(shifts) == 4
    kitchen_shifts = [s for s in shifts if s.role == Role.KITCHEN]
    assert len(kitchen_shifts) == 2
    for s in shifts:
        staff = store.get_staff(s.staff_id)
        assert s.role in staff.roles


def test_assign_shifts_boss_absent_adds_one(store):
    needs = {"后厨": 2, "传菜": 1, "收银": 1}
    shifts_normal = assign_shifts(store, "2026-05-20", "早班", needs, boss_absent=False)
    shifts_absent = assign_shifts(store, "2026-05-20", "早班", needs, boss_absent=True)
    assert len(shifts_absent) == len(shifts_normal) + 1


def test_find_replacement(store):
    shifts = assign_shifts(store, "2026-05-20", "早班",
                           {"后厨": 2, "传菜": 1, "收银": 1}, boss_absent=False)
    absentee = shifts[0].staff_id
    candidates = find_replacement(store, absentee, shifts, "2026-05-20")
    assert absentee not in [c.id for c in candidates]
    for c in candidates:
        absent_staff = store.get_staff(absentee)
        assert any(r in c.roles for r in absent_staff.roles)


def test_generate_weekly_schedule(store):
    schedule = generate_weekly_schedule(store, "2026-05-18")
    assert schedule.week_start == "2026-05-18"
    assert len(schedule.shifts) > 0
    dates = {s.date for s in schedule.shifts}
    assert len(dates) >= 5
