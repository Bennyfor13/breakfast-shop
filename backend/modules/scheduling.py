from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import Staff, Role, Shift, Schedule, AttendanceLog


def get_staffing_needs(store: AbstractStore, day: str, period: str) -> dict[str, int]:
    template = store.get_demand_template()
    key = f"{day}-{period}"
    return template.entries.get(key, {})


def _staff_can_do(staff: Staff, role: Role) -> bool:
    return role in staff.roles


def assign_shifts(
    store: AbstractStore, date: str, period: str,
    needs: dict[str, int], boss_absent: bool = False,
) -> list[Shift]:
    active = store.list_staff()
    shifts: list[Shift] = []

    for role_str, count in needs.items():
        role = Role(role_str)
        candidates = [s for s in active if _staff_can_do(s, role)]
        assigned = 0
        for staff in candidates:
            if assigned >= count:
                break
            shifts.append(Shift(staff_id=staff.id, date=date, period=period, role=role))
            assigned += 1

    if boss_absent:
        # Add an extra shift for any active staff member
        for staff in active:
            shifts.append(Shift(
                staff_id=staff.id, date=date, period=period,
                role=Role.SERVICE,
            ))
            break

    return shifts


def edit_shift(
    store: AbstractStore, date: str, period: str,
    old_staff_id: str, new_staff_id: str,
) -> bool:
    """Replace one staff member with another in a specific shift slot."""
    from datetime import datetime, timedelta
    shifts_on_date = store.get_shifts_by_date(date)
    if not any(s.period == period and s.staff_id == old_staff_id for s in shifts_on_date):
        return False
    dt = datetime.strptime(date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    all_week_shifts = store.get_shifts(week_start)
    for s in all_week_shifts:
        if s.date == date and s.period == period and s.staff_id == old_staff_id:
            s.staff_id = new_staff_id
            break
    store.save_shifts(all_week_shifts)
    return True


def assign_replacement(
    store: AbstractStore, absent_id: str, date: str,
    replacement_id: str | None = None,
) -> dict:
    """Find and assign a replacement. Uses replacement_id if given, else auto-picks."""
    existing = store.get_shifts_by_date(date)
    absent_shifts = [s for s in existing if s.staff_id == absent_id]
    if not absent_shifts:
        return {"assigned": False, "shifts_replaced": 0, "reason": "该员工当日无排班"}

    if replacement_id:
        candidate = store.get_staff(replacement_id)
        if not candidate:
            return {"assigned": False, "shifts_replaced": 0, "reason": "替班员工不存在"}
        absent = store.get_staff(absent_id)
        if not any(r in candidate.roles for r in absent.roles):
            return {"assigned": False, "shifts_replaced": 0, "reason": "替班员工无法胜任缺勤者的角色"}
    else:
        candidates = find_replacement(store, absent_id, existing, date)
        if not candidates:
            return {"assigned": False, "shifts_replaced": 0, "reason": "无合适的替班人选"}
        replacement_id = candidates[0].id

    from datetime import datetime, timedelta
    dt = datetime.strptime(date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    all_week_shifts = store.get_shifts(week_start)
    replaced = 0
    for s in all_week_shifts:
        if s.date == date and s.staff_id == absent_id:
            s.staff_id = replacement_id
            replaced += 1
    store.save_shifts(all_week_shifts)

    log = store.get_attendance(date)
    if log:
        log.substitute[absent_id] = replacement_id
        store.save_attendance(log)
    else:
        store.save_attendance(AttendanceLog(date=date, substitute={absent_id: replacement_id}))

    return {"assigned": True, "replacement_id": replacement_id, "shifts_replaced": replaced}


def find_replacement(
    store: AbstractStore, absent_id: str, existing_shifts: list[Shift], date: str,
) -> list[Staff]:
    absent = store.get_staff(absent_id)
    if not absent:
        return []
    existing_ids = {s.staff_id for s in existing_shifts}
    active = store.list_staff()
    candidates = [
        s for s in active
        if s.id != absent_id and s.id not in existing_ids
        and any(r in s.roles for r in absent.roles)
    ]
    return candidates


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PERIODS = ["early", "late"]


def generate_weekly_schedule(
    store: AbstractStore, week_start: str, boss_absent_dates: set[str] | None = None,
) -> Schedule:
    from datetime import datetime, timedelta
    start = datetime.strptime(week_start, "%Y-%m-%d")
    absent_dates = boss_absent_dates or set()
    all_shifts: list[Shift] = []

    for i in range(7):
        d = start + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_name = DAYS[d.weekday()]
        for period in PERIODS:
            needs = get_staffing_needs(store, day_name, period)
            if not needs:
                # Fall back to Monday's template for days without specific entries
                needs = get_staffing_needs(store, "Monday", period)
                if not needs:
                    needs = get_staffing_needs(store, "Monday", "early")
            boss_absent = date_str in absent_dates
            period_cn = "早班" if period == "early" else "晚班"
            shifts = assign_shifts(store, date_str, period_cn, needs, boss_absent)
            all_shifts.extend(shifts)

    return Schedule(week_start=week_start, shifts=all_shifts)
