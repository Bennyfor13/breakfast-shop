from backend.data.models import Shift, Role, AttendanceLog
from backend.modules.scheduling import edit_shift, assign_replacement
from backend.modules.payroll import count_shifts_worked, calculate_salary


def seed_week_shifts(store):
    shifts = [
        Shift(staff_id="s1", date="2026-05-18", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s1", date="2026-05-19", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s2", date="2026-05-19", period="早班", role=Role.SERVICE),
    ]
    store.save_shifts(shifts)


def test_edit_shift_success(store):
    seed_week_shifts(store)
    assert edit_shift(store, "2026-05-19", "早班", "s1", "s3")
    shifts = store.get_shifts_by_date("2026-05-19")
    assert any(s.staff_id == "s3" and s.period == "早班" for s in shifts)
    assert not any(s.staff_id == "s1" and s.period == "早班" for s in shifts)


def test_edit_shift_not_found(store):
    seed_week_shifts(store)
    assert not edit_shift(store, "2026-05-19", "晚班", "s1", "s3")


def test_assign_replacement_auto(store):
    seed_week_shifts(store)
    result = assign_replacement(store, "s1", "2026-05-19")
    assert result["assigned"]
    assert result["replacement_id"] == "s3"  # s3 is KITCHEN like s1
    shifts = store.get_shifts_by_date("2026-05-19")
    assert not any(s.staff_id == "s1" for s in shifts)
    # s3 should now have a shift on that date
    assert any(s.staff_id == "s3" and s.period == "早班" for s in shifts)


def test_assign_replacement_specific(store):
    seed_week_shifts(store)
    result = assign_replacement(store, "s1", "2026-05-19", replacement_id="s3")
    assert result["assigned"]
    assert result["replacement_id"] == "s3"


def test_assign_replacement_no_absent_shifts(store):
    seed_week_shifts(store)
    result = assign_replacement(store, "s2", "2026-05-20")  # s2 has no shift on 20th
    assert not result["assigned"]
    assert "无排班" in result["reason"]


def test_assign_replacement_writes_attendance(store):
    seed_week_shifts(store)
    assign_replacement(store, "s1", "2026-05-19", replacement_id="s3")
    log = store.get_attendance("2026-05-19")
    assert log is not None
    assert log.substitute.get("s1") == "s3"


def test_payroll_counts_substitute_shifts(store):
    """When s1 is absent on 2026-05-19 and s3 subs, s3 gets s1's shift counted."""
    shifts = [
        Shift(staff_id="s1", date="2026-05-19", period="早班", role=Role.KITCHEN),
    ]
    store.save_shifts(shifts)
    store.save_attendance(AttendanceLog(
        date="2026-05-19", absent=["s1"], substitute={"s1": "s3"},
    ))
    counts = count_shifts_worked(store, "s3", "2026-05-18", "2026-05-24")
    assert counts["早班"] == 1


def test_payroll_counts_overtime(store):
    shifts = [
        Shift(staff_id="s1", date="2026-05-19", period="早班", role=Role.KITCHEN),
    ]
    store.save_shifts(shifts)
    store.save_attendance(AttendanceLog(
        date="2026-05-19", overtime=["s1"],
    ))
    salary = calculate_salary(store, "s1", "2026-05-18", "2026-05-24")
    assert salary["overtime_shifts"] == 1
    assert salary["base_pay"] == 80 + 60 * 1.5  # morning 80 + overtime 90
    assert salary["total"] == salary["base_pay"] + salary["performance_bonus"]
