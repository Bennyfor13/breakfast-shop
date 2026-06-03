from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import Staff, Shift, Schedule, AttendanceLog


def get_staffing_needs(store: AbstractStore, day: str, period: str) -> int:
    template = store.get_demand_template()
    key = f"{day}-{period}"
    return template.entries.get(key, 0)


def assign_shifts(
    store: AbstractStore, date: str, period: str,
    count: int, shift_counts: dict[str, int],
    daily_assigned: dict[str, int] | None = None,
) -> list[Shift]:
    """Assign `count` staff for one period, preferring those with fewer weekly shifts
    and avoiding double shifts (morning+evening same day) when possible."""
    active = store.list_staff()
    shifts: list[Shift] = []
    daily = daily_assigned or {}

    candidates = sorted(active, key=lambda s: (
        shift_counts.get(s.id, 0),
        daily.get(s.id, 0),
    ))

    for staff in candidates:
        if len(shifts) >= count:
            break
        shifts.append(Shift(staff_id=staff.id, date=date, period=period))
        shift_counts[staff.id] = shift_counts.get(staff.id, 0) + 1
        daily[staff.id] = daily.get(staff.id, 0) + 1

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


def set_cell_shifts(
    store: AbstractStore, date: str, period: str,
    staff_shifts: list[dict],
) -> list[Shift]:
    """Replace all shifts for a date+period with the given staff_shifts.
    Each item: {"staff_id": str, "hours": float}"""
    from datetime import datetime, timedelta

    dt = datetime.strptime(date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    all_shifts = store.get_shifts(week_start)

    kept = [s for s in all_shifts if not (s.date == date and s.period == period)]

    new_shifts = []
    for item in staff_shifts:
        sid = item["staff_id"]
        hours = item.get("hours", 11)
        shift = Shift(staff_id=sid, date=date, period=period, hours=hours)
        kept.append(shift)
        new_shifts.append(shift)

    store.save_shifts(kept)
    return new_shifts


def set_day_shifts(
    store: AbstractStore, date: str,
    staff_shifts: list[dict],
) -> list[Shift]:
    """Replace ALL shifts for a single date. Each item: {"staff_id": str, "hours": float}
    Period defaults to "早班" for backward compat."""
    from datetime import datetime, timedelta
    dt = datetime.strptime(date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    all_shifts = store.get_shifts(week_start)

    kept = [s for s in all_shifts if s.date != date]
    new_shifts = []
    for item in staff_shifts:
        sid = item["staff_id"]
        hours = item.get("hours", 11)
        shift = Shift(staff_id=sid, date=date, period="早班", hours=hours)
        kept.append(shift)
        new_shifts.append(shift)

    store.save_shifts(kept)
    return new_shifts


def move_shift(
    store: AbstractStore, staff_id: str,
    from_date: str, from_period: str,
    to_date: str, to_period: str,
) -> bool:
    """Move a staff member from one shift slot to another. Returns True on success."""
    from datetime import datetime, timedelta

    dt = datetime.strptime(from_date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    all_shifts = store.get_shifts(week_start)

    removed = False
    kept = []
    for s in all_shifts:
        if s.date == from_date and s.period == from_period and s.staff_id == staff_id:
            removed = True
            continue
        kept.append(s)
    if not removed:
        return False

    kept.append(Shift(staff_id=staff_id, date=to_date, period=to_period))
    store.save_shifts(kept)
    return True


def auto_reschedule_day(
    store: AbstractStore, staff_id: str, date_str: str,
) -> dict:
    """Automatically find and assign replacements for all shifts of a staff member
    on a given date. Returns a summary dict with results."""
    from datetime import datetime, timedelta

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")

    all_week = store.get_shifts(week_start)
    existing = store.get_shifts_by_date(date_str)
    absent_shifts = [s for s in existing if s.staff_id == staff_id]
    if not absent_shifts:
        return {"ok": False, "reason": f"该员工在 {date_str} 无排班", "replacements": []}

    # Track shift counts for fair replacement selection
    active = store.list_staff()
    shift_counts: dict[str, int] = {}
    for s in all_week:
        shift_counts[s.staff_id] = shift_counts.get(s.staff_id, 0) + 1

    replacements = []
    for shift in absent_shifts:
        # Find best candidate: not the absent person, not already working this period,
        # with fewest shifts this week
        busy_ids = {s.staff_id for s in existing if s.period == shift.period}
        busy_ids.add(staff_id)
        candidates = sorted(
            [s for s in active if s.id not in busy_ids],
            key=lambda s: shift_counts.get(s.id, 0),
        )
        if not candidates:
            continue
        replacement = candidates[0]
        # Update the shift in all_week
        for s in all_week:
            if s.date == date_str and s.period == shift.period and s.staff_id == staff_id:
                s.staff_id = replacement.id
                break
        shift_counts[replacement.id] = shift_counts.get(replacement.id, 0) + 1
        busy_ids.add(replacement.id)
        replacements.append({
            "date": date_str,
            "period": shift.period,
            "original": staff_id,
            "replacement_id": replacement.id,
            "replacement_name": replacement.name,
        })

    store.save_shifts(all_week)

    # Record attendance
    log = store.get_attendance(date_str)
    if log:
        if staff_id not in log.absent:
            log.absent.append(staff_id)
    else:
        from backend.data.models import AttendanceLog
        log = AttendanceLog(date=date_str, absent=[staff_id])
    for r in replacements:
        log.substitute[staff_id] = r["replacement_id"]
    store.save_attendance(log)

    return {"ok": True, "date": date_str, "replacements": replacements}


def find_replacement(
    store: AbstractStore, absent_id: str, existing_shifts: list[Shift], date: str,
) -> list[Staff]:
    existing_ids = {s.staff_id for s in existing_shifts}
    active = store.list_staff()
    return [s for s in active if s.id != absent_id and s.id not in existing_ids]


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PERIODS = ["early", "late"]


def generate_weekly_schedule(
    store: AbstractStore, week_start: str, boss_absent_dates: set[str] | None = None,
) -> Schedule:
    from datetime import datetime, timedelta
    start = datetime.strptime(week_start, "%Y-%m-%d")
    all_shifts: list[Shift] = []
    shift_counts: dict[str, int] = {}

    for i in range(7):
        d = start + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_name = DAYS[d.weekday()]
        daily_assigned: dict[str, int] = {}
        for period in PERIODS:
            count = get_staffing_needs(store, day_name, period)
            if not count:
                count = get_staffing_needs(store, "Monday", period)
                if not count:
                    count = get_staffing_needs(store, "Monday", "early")
            period_cn = "早班" if period == "early" else "晚班"
            shifts = assign_shifts(store, date_str, period_cn, count, shift_counts, daily_assigned)
            all_shifts.extend(shifts)

    return Schedule(week_start=week_start, shifts=all_shifts)


def auto_reschedule_multiple_days(
    store: AbstractStore,
    staff_id: str,
    dates: list[str]
) -> dict:
    """处理某人多天请假，自动找替班人"""
    from datetime import datetime, timedelta

    all_suggestions = []

    for date_str in dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        monday = dt - timedelta(days=dt.weekday())
        week_start = monday.strftime("%Y-%m-%d")

        all_week = store.get_shifts(week_start)
        if not all_week:
            schedule = generate_weekly_schedule(store, week_start)
            store.save_shifts(schedule.shifts)
            all_week = schedule.shifts

        existing = store.get_shifts_by_date(date_str)
        absent_shifts = [s for s in existing if s.staff_id == staff_id]

        if not absent_shifts:
            continue

        shift_counts = {}
        for s in all_week:
            shift_counts[s.staff_id] = shift_counts.get(s.staff_id, 0) + 1

        for shift in absent_shifts:
            busy_ids = {s.staff_id for s in existing if s.period == shift.period}
            busy_ids.add(staff_id)

            candidates = find_replacement(store, staff_id, existing, date_str)
            candidates = [c for c in candidates if c.id not in busy_ids]
            candidates = sorted(candidates, key=lambda c: shift_counts.get(c.id, 0))

            if candidates:
                replacement = candidates[0]
                all_suggestions.append({
                    "date": date_str,
                    "period": shift.period,
                    "original": staff_id,
                    "replacement_id": replacement.id,
                    "replacement_name": replacement.name
                })

    return {
        "ok": True if all_suggestions else False,
        "suggestions": all_suggestions,
        "reason": "该员工在指定日期无排班" if not all_suggestions else None
    }


def cancel_staff_for_week(
    store: AbstractStore,
    staff_id: str,
    week_start: str,
    period_filter: str | None = None
) -> dict:
    """取消某人整周（或整周某时段）的班次，自动找替班"""
    all_week = store.get_shifts(week_start)
    if not all_week:
        schedule = generate_weekly_schedule(store, week_start)
        store.save_shifts(schedule.shifts)
        all_week = schedule.shifts

    target_shifts = [
        s for s in all_week
        if s.staff_id == staff_id and (period_filter is None or s.period == period_filter)
    ]

    if not target_shifts:
        return {
            "ok": False,
            "reason": f"该员工本周{'所有' if not period_filter else period_filter}班次为空"
        }

    shift_counts = {}
    for s in all_week:
        shift_counts[s.staff_id] = shift_counts.get(s.staff_id, 0) + 1

    replacements = []
    active = store.list_staff()

    for shift in target_shifts:
        existing_on_date = [s for s in all_week if s.date == shift.date]
        busy_ids = {s.staff_id for s in existing_on_date if s.period == shift.period}
        busy_ids.add(staff_id)

        candidates = sorted(
            [s for s in active if s.id not in busy_ids],
            key=lambda s: shift_counts.get(s.id, 0)
        )

        if candidates:
            replacement = candidates[0]
            replacements.append({
                "date": shift.date,
                "period": shift.period,
                "original": staff_id,
                "replacement_id": replacement.id,
                "replacement_name": replacement.name
            })
            shift_counts[replacement.id] = shift_counts.get(replacement.id, 0) + 1
        else:
            replacements.append({
                "date": shift.date,
                "period": shift.period,
                "original": staff_id,
                "replacement_id": None,
                "replacement_name": "无合适人选"
            })

    return {
        "ok": True,
        "affected_shifts": len(target_shifts),
        "replacements": replacements
    }
