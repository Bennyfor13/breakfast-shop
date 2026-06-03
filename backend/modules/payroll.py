from __future__ import annotations
from datetime import datetime, timedelta

from backend.data.interface import AbstractStore


def _gen_week_starts(from_date: str, to_date: str):
    """Generate Monday-aligned week-start dates covering [from_date, to_date]."""
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    # Start from the Monday of the week containing from_date
    cursor = from_dt - timedelta(days=from_dt.weekday())
    while cursor <= to_dt:
        yield cursor.strftime("%Y-%m-%d")
        cursor += timedelta(days=7)


def _total_month_hours(
    store: AbstractStore, staff_id: str, from_date: str, to_date: str,
) -> float:
    """计算员工某月总上班小时数（排除缺勤日）"""
    total = 0.0
    for week_start in _gen_week_starts(from_date, to_date):
        all_shifts = store.get_shifts(week_start)
        for s in all_shifts:
            if s.staff_id == staff_id and from_date <= s.date <= to_date:
                total += s.hours or 11  # 默认全天11小时

    # 扣除缺勤日的工时
    attendance = store.list_attendance(from_date, to_date)
    for a in attendance:
        if staff_id in a.absent:
            for week_start in _gen_week_starts(from_date, to_date):
                for s in store.get_shifts(week_start):
                    if s.staff_id == staff_id and s.date == a.date:
                        total -= s.hours or 11

    return max(0, total)


def calculate_salary(
    store: AbstractStore, staff_id: str, from_date: str, to_date: str,
) -> dict:
    staff = store.get_staff(staff_id)
    if not staff:
        return {}

    total_hours = _total_month_hours(store, staff_id, from_date, to_date)
    hourly_wage = staff.hourly_wage or 15

    # Count working days in the month
    working_days = 0
    for week_start in _gen_week_starts(from_date, to_date):
        for s in store.get_shifts(week_start):
            if s.staff_id == staff_id and from_date <= s.date <= to_date and s.hours > 0:
                working_days += 1

    # Count total days in this month
    from calendar import monthrange
    _, total_days = monthrange(int(from_date[:4]), int(from_date[5:7]))

    # Full attendance = rest days ≤ 2
    rest_days = total_days - working_days
    # Full attendance (auto-calc) and commission (manual input)
    full_attendance = (rest_days <= 2 and working_days > 0)
    full_attendance_bonus = store.get_staff_bonus(staff_id, f"{from_date[:7]}|fa") or 0
    commission = store.get_staff_bonus(staff_id, from_date[:7]) or 0

    base_pay = round(total_hours * hourly_wage, 1)
    subtotal = round(base_pay + full_attendance_bonus + commission, 1)

    return {
        "staff_id": staff.id,
        "staff_name": staff.name,
        "total_hours": total_hours,
        "hourly_wage": hourly_wage,
        "working_days": working_days,
        "rest_days": rest_days,
        "full_attendance": full_attendance,
        "full_attendance_bonus": full_attendance_bonus,
        "base_pay": base_pay,
        "commission": commission,
        "total": subtotal,
    }


def generate_monthly_payroll(
    store: AbstractStore, year_month: str,
) -> list[dict]:
    from calendar import monthrange
    from backend.modules.scheduling import generate_weekly_schedule

    year, month = int(year_month[:4]), int(year_month[5:7])
    _, last_day = monthrange(year, month)
    from_date = f"{year_month}-01"
    to_date = f"{year_month}-{last_day:02d}"

    # Auto-generate schedules for any missing weeks in the month
    for week_start in _gen_week_starts(from_date, to_date):
        existing = store.get_shifts(week_start)
        if not existing:
            schedule = generate_weekly_schedule(store, week_start)
            store.save_shifts(schedule.shifts)

    results = []
    for staff in store.list_staff():
        salary = calculate_salary(store, staff.id, from_date, to_date)
        if salary.get("base_pay", 0) > 0 or salary.get("bonus", 0) > 0:
            results.append(salary)
    return results


def set_monthly_bonus(
    store: AbstractStore, staff_id: str, year_month: str, bonus: float,
) -> None:
    """设置员工某月奖金"""
    store.set_staff_bonus(staff_id, year_month, bonus)
