from backend.data.models import Shift, Role, AttendanceLog, PerformanceScore
from backend.modules.payroll import (
    count_shifts_worked, calculate_salary, generate_monthly_payroll,
)


def seed_shifts_and_attendance(store):
    """Seed a week of shifts + one absent day."""
    shifts = [
        Shift(staff_id="s1", date="2026-05-18", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s1", date="2026-05-19", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s1", date="2026-05-20", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s1", date="2026-05-21", period="早班", role=Role.KITCHEN),
        Shift(staff_id="s1", date="2026-05-20", period="晚班", role=Role.KITCHEN),
    ]
    store.save_shifts(shifts)
    store.save_attendance(AttendanceLog(
        date="2026-05-21",
        absent=["s1"],
        substitute={},
        overtime=[],
    ))
    store.save_performance(PerformanceScore(staff_id="s1", date=None, score=4.0))


def test_count_shifts_worked(store):
    seed_shifts_and_attendance(store)
    counts = count_shifts_worked(store, "s1", "2026-05-18", "2026-05-24")
    # s1: 3 morning shifts (absent on 21st) + 1 evening shift
    assert counts["早班"] == 3
    assert counts["晚班"] == 1


def test_calculate_salary(store):
    seed_shifts_and_attendance(store)
    salary = calculate_salary(store, "s1", "2026-05-18", "2026-05-24")
    # morning: 3 x 80 = 240, evening: 1 x 60 = 60, base = 300
    # perf 4.0/5 -> bonus = (4-3)/5 * base = 20%
    assert salary["morning_shifts"] == 3
    assert salary["evening_shifts"] == 1
    assert salary["base_pay"] == 300
    assert salary["performance_bonus"] == 60
    assert salary["total"] == 360


def test_generate_monthly_payroll(store):
    seed_shifts_and_attendance(store)
    payroll = generate_monthly_payroll(store, "2026-05")
    assert len(payroll) >= 1
    s1_entry = next(p for p in payroll if p["staff_name"] == "张三")
    assert s1_entry["total"] > 0
