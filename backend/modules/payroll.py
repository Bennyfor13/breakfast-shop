from __future__ import annotations
from datetime import datetime, timedelta

from backend.data.interface import AbstractStore


def _gen_week_starts(from_date: str, to_date: str):
    """Generate week-start dates covering [from_date, to_date]."""
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    cursor = from_dt
    while cursor <= to_dt:
        yield cursor.strftime("%Y-%m-%d")
        cursor += timedelta(days=7)


def count_shifts_worked(
    store: AbstractStore, staff_id: str, from_date: str, to_date: str,
) -> dict[str, int]:
    """Returns {"早班": N, "晚班": M} excluding absent days, including substitute shifts."""
    all_shifts = []
    for week_start in _gen_week_starts(from_date, to_date):
        all_shifts.extend(store.get_shifts(week_start))

    shifts = [
        s for s in all_shifts
        if s.staff_id == staff_id and from_date <= s.date <= to_date
    ]
    attendance = store.list_attendance(from_date, to_date)
    absent_dates: set[str] = set()
    for a in attendance:
        if staff_id in a.absent:
            absent_dates.add(a.date)

    counts: dict[str, int] = {"早班": 0, "晚班": 0}
    for s in shifts:
        if s.date not in absent_dates:
            counts[s.period] = counts.get(s.period, 0) + 1

    # Add substitute shifts (shifts from absent staff this staff is covering)
    for a in attendance:
        for absent_id, sub_id in a.substitute.items():
            if sub_id == staff_id:
                for s in all_shifts:
                    if s.staff_id == absent_id and s.date == a.date:
                        counts[s.period] = counts.get(s.period, 0) + 1

    return counts


def calculate_salary(
    store: AbstractStore, staff_id: str, from_date: str, to_date: str,
) -> dict:
    staff = store.get_staff(staff_id)
    if not staff:
        return {}

    counts = count_shifts_worked(store, staff_id, from_date, to_date)

    # Overtime
    attendance = store.list_attendance(from_date, to_date)
    overtime_count = sum(1 for a in attendance if staff_id in a.overtime)

    morning_pay = counts.get("早班", 0) * staff.morning_rate
    evening_pay = counts.get("晚班", 0) * staff.evening_rate
    overtime_pay = overtime_count * staff.evening_rate * 1.5
    base = morning_pay + evening_pay + overtime_pay

    scores = store.get_performance(staff_id, from_date, to_date)
    avg_score = sum(s.score for s in scores) / len(scores) if scores else 3.0
    bonus_rate = (avg_score - 3) / 5  # 3->0%, 4->20%, 5->40%
    bonus = round(base * max(0, bonus_rate), 0)

    return {
        "staff_name": staff.name,
        "morning_shifts": counts.get("早班", 0),
        "evening_shifts": counts.get("晚班", 0),
        "overtime_shifts": overtime_count,
        "morning_rate": staff.morning_rate,
        "evening_rate": staff.evening_rate,
        "base_pay": base,
        "performance_score": round(avg_score, 1),
        "performance_bonus": bonus,
        "total": base + bonus,
    }


def generate_monthly_payroll(
    store: AbstractStore, year_month: str,
) -> list[dict]:
    from calendar import monthrange
    year, month = int(year_month[:4]), int(year_month[5:7])
    _, last_day = monthrange(year, month)
    from_date = f"{year_month}-01"
    to_date = f"{year_month}-{last_day:02d}"

    results = []
    for staff in store.list_staff():
        salary = calculate_salary(store, staff.id, from_date, to_date)
        if salary.get("total", 0) > 0:
            results.append(salary)
    return results
