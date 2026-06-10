from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Depends
from backend.data.mock_store import MockStore
from backend.data.models import (
    Staff, Role, MenuItem, Ingredient, DemandTemplate, Schedule,
    AttendanceLog, PerformanceScore, IngredientStock, WasteFeedback,
)
from backend.auth import get_current_user
from backend.modules.base_data import (
    create_staff, list_active_staff, update_staff, remove_staff,
    create_menu_item, list_active_menu, get_bom_for_item, remove_menu_item,
)
from backend.modules.scheduling import (
    find_replacement,
    edit_shift, assign_replacement, move_shift, set_cell_shifts,
)
from backend.modules.inventory import (
    forecast_ingredient_needs, generate_purchase_list,
)
from backend.modules.pricing import analyze_all_items
from backend.modules.payroll import generate_monthly_payroll

router = APIRouter(prefix="/api")
store = MockStore.load_or_create()


# -- Staff --
@router.get("/staff")
def api_list_staff():
    return [s.model_dump() for s in list_active_staff(store)]


@router.post("/staff")
def api_create_staff(name: str, roles: list[str] = Query(...), morning_rate: float = 80, evening_rate: float = 60, note: str = "", user_id: str = Depends(get_current_user)):
    role_enums = [Role(r) for r in roles]
    staff = create_staff(store, None, name, role_enums, morning_rate, evening_rate, note)
    return staff.model_dump()


@router.put("/staff/{staff_id}")
def api_update_staff(staff_id: str, data: dict, user_id: str = Depends(get_current_user)):
    result = update_staff(store, staff_id, **data)
    if not result:
        raise HTTPException(404)
    return result.model_dump()


@router.delete("/staff/{staff_id}")
def api_delete_staff(staff_id: str, user_id: str = Depends(get_current_user)):
    remove_staff(store, staff_id)
    return {"ok": True}


# -- Menu --
@router.get("/menu")
def api_list_menu():
    return [m.model_dump() for m in list_active_menu(store)]


@router.post("/menu")
def api_create_menu(name: str, price: float, bom: list[dict] = [], user_id: str = Depends(get_current_user)):
    ingredients = [Ingredient(**i) for i in bom]
    item = create_menu_item(store, None, name, price, ingredients)
    return item.model_dump()


@router.get("/menu/{item_id}/bom")
def api_get_bom(item_id: str):
    return [i.model_dump() for i in get_bom_for_item(store, item_id)]


@router.delete("/menu/{item_id}")
def api_delete_menu(item_id: str, user_id: str = Depends(get_current_user)):
    remove_menu_item(store, item_id)
    return {"ok": True}


# -- Demand Template --
@router.get("/demand-template")
def api_get_demand():
    return store.get_demand_template().model_dump()


@router.put("/demand-template")
def api_set_demand(data: dict, user_id: str = Depends(get_current_user)):
    template = DemandTemplate(entries=data.get("entries", {}))
    store.set_demand_template(template)
    return {"ok": True}


# -- Schedule --
@router.get("/schedule/month")
def api_get_month_schedule(year_month: str):
    """Return all shifts for a month (existing only, no auto-generation)."""
    from calendar import monthrange
    from backend.modules.payroll import _gen_week_starts

    year, month = int(year_month[:4]), int(year_month[5:7])
    _, last_day = monthrange(year, month)
    from_date = f"{year_month}-01"
    to_date = f"{year_month}-{last_day:02d}"

    all_shifts = []
    for week_start in _gen_week_starts(from_date, to_date):
        all_shifts.extend(store.get_shifts(week_start))

    # Build per-person summary (hours-based)
    staff_list = [s.model_dump() for s in store.list_staff()]
    summary: dict[str, dict] = {}
    for s in staff_list:
        summary[s["id"]] = {
            "staff_id": s["id"],
            "staff_name": s["name"],
            "days_worked": 0,
            "total_hours": 0.0,
            "hourly_wage": s.get("hourly_wage", 15),
        }
    seen_dates: dict[str, set] = {}
    for shift in all_shifts:
        if shift.staff_id in summary and from_date <= shift.date <= to_date:
            summary[shift.staff_id]["total_hours"] += shift.hours or 11
            if shift.staff_id not in seen_dates:
                seen_dates[shift.staff_id] = set()
            if shift.date not in seen_dates[shift.staff_id]:
                seen_dates[shift.staff_id].add(shift.date)
                summary[shift.staff_id]["days_worked"] += 1

    for s in summary.values():
        s["estimated_pay"] = round(s["total_hours"] * s["hourly_wage"], 1)

    return {
        "year_month": year_month,
        "shifts": [s.model_dump() for s in all_shifts],
        "summary": sorted(summary.values(), key=lambda x: x["staff_name"]),
        "staff": staff_list,
    }


@router.get("/schedule")
def api_get_schedule(week_start: str, boss_absent: str = "", regenerate: str = ""):
    existing = store.get_shifts(week_start)
    return Schedule(week_start=week_start, shifts=existing).model_dump()


@router.get("/schedule/replacement")
def api_find_replacement(absent_id: str, date: str):
    existing = store.get_shifts_by_date(date)
    candidates = find_replacement(store, absent_id, existing, date)
    return [c.model_dump() for c in candidates]


@router.post("/schedule/edit")
def api_edit_shift(data: dict, user_id: str = Depends(get_current_user)):
    success = edit_shift(
        store, data["date"], data["period"],
        data["old_staff_id"], data["new_staff_id"],
    )
    if not success:
        raise HTTPException(404, "Shift not found")
    return {"ok": True}


@router.post("/payroll/bonus")
def api_set_bonus(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.payroll import set_monthly_bonus
    set_monthly_bonus(store, data["staff_id"], data["year_month"], data.get("bonus", 0))
    return {"ok": True}


@router.post("/schedule/cell")
def api_set_cell(data: dict, user_id: str = Depends(get_current_user)):
    # Support both new format (staff_shifts) and old format (staff_ids)
    staff_shifts = data.get("staff_shifts")
    if staff_shifts is None:
        staff_shifts = [{"staff_id": sid, "hours": 11} for sid in data.get("staff_ids", [])]
    shifts = set_cell_shifts(store, data["date"], data["period"], staff_shifts)
    return {"ok": True, "shifts": [s.model_dump() for s in shifts]}


@router.post("/schedule/day")
def api_set_day(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.scheduling import set_day_shifts
    shifts = set_day_shifts(store, data["date"], data.get("staff_shifts", []))
    return {"ok": True, "shifts": [s.model_dump() for s in shifts]}


@router.post("/schedule/clear-week")
def api_clear_week(week_start: str, user_id: str = Depends(get_current_user)):
    from datetime import datetime, timedelta
    dt = datetime.strptime(week_start, "%Y-%m-%d")
    end = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
    all_shifts = store.get_shifts(week_start)
    kept = [s for s in all_shifts if s.date < week_start or s.date >= end]
    store.shifts = kept
    store._save()
    return {"ok": True}


@router.post("/schedule/clear-month")
def api_clear_month(year_month: str, user_id: str = Depends(get_current_user)):
    from calendar import monthrange
    from backend.modules.payroll import _gen_week_starts
    from_date = f"{year_month}-01"
    _, last_day = monthrange(int(year_month[:4]), int(year_month[5:7]))
    to_date = f"{year_month}-{last_day:02d}"
    kept = [s for s in store.shifts if s.date < from_date or s.date > to_date]
    store.shifts = kept
    store._save()
    return {"ok": True}


@router.post("/schedule/move")
def api_move_shift(data: dict, user_id: str = Depends(get_current_user)):
    success = move_shift(
        store,
        staff_id=data["staff_id"],
        from_date=data["from_date"],
        from_period=data["from_period"],
        to_date=data["to_date"],
        to_period=data["to_period"],
    )
    if not success:
        raise HTTPException(404, "Source shift not found")
    return {"ok": True}


@router.post("/schedule/assign-replacement")
def api_assign_replacement(data: dict, user_id: str = Depends(get_current_user)):
    result = assign_replacement(
        store, data["absent_id"], data["date"],
        data.get("replacement_id"),
    )
    if not result["assigned"]:
        raise HTTPException(400, result.get("reason", "Assignment failed"))
    return result


# -- Inventory --
@router.get("/inventory/stocks")
def api_list_stocks():
    return [s.model_dump() for s in store.list_stocks()]


@router.get("/inventory/forecast")
def api_forecast(sales: str = ""):
    # sales: "m1:100,m2:50"
    predicted = {}
    for pair in sales.split(","):
        if ":" in pair:
            k, v = pair.split(":")
            predicted[k.strip()] = int(v.strip())
    needs = forecast_ingredient_needs(store, predicted)
    purchases = generate_purchase_list(store, needs)
    return {"needs": needs, "purchases": purchases}


@router.post("/waste")
def api_save_waste(data: dict, user_id: str = Depends(get_current_user)):
    fb = WasteFeedback(**data)
    store.save_waste(fb)
    return {"ok": True}


# -- Attendance --
@router.post("/attendance")
def api_save_attendance(data: dict, user_id: str = Depends(get_current_user)):
    log = AttendanceLog(**data)
    store.save_attendance(log)
    return {"ok": True}


# -- Performance --
@router.post("/performance")
def api_save_performance(data: dict, user_id: str = Depends(get_current_user)):
    score = PerformanceScore(**data)
    store.save_performance(score)
    return {"ok": True}


# -- Dashboard overview (combined endpoint for speed) --
@router.get("/dashboard")
def api_dashboard():
    from datetime import date, timedelta
    from calendar import monthrange
    from backend.modules.payroll import _gen_week_starts
    today = date.today().strftime("%Y-%m-%d")
    year_month = today[:7]

    # Today shifts
    shifts_today = store.get_shifts_by_date(today)
    today_staff = [{"staff_id": s.staff_id, "hours": s.hours or 11} for s in shifts_today]

    staff_list = [s.model_dump() for s in store.list_staff()]

    # Accounting summary
    from backend.modules.accounting import get_monthly_accounting
    accounting = get_monthly_accounting(store, year_month)

    # Monthly wages - fast estimate (skip full payroll calc)
    from backend.modules.payroll import _total_month_hours
    from calendar import monthrange
    year = int(year_month[:4])
    month = int(year_month[5:7])
    _, last_day = monthrange(year, month)
    from_date = f"{year_month}-01"
    to_date = f"{year_month}-{last_day:02d}"

    total_wages = 0
    for s in store.list_staff():
        hours = _total_month_hours(store, s.id, from_date, to_date)
        wage = s.hourly_wage or 15
        base = hours * wage
        bonus = store.get_staff_bonus(s.id, year_month) or 0
        fa_bonus = store.get_staff_bonus(s.id, f"{year_month}|fa") or 0
        total_wages += base + bonus + fa_bonus

    return {
        "date": today,
        "today_staff": today_staff,
        "staff": staff_list,
        "accounting": accounting,
        "total_wages": round(total_wages, 1),
    }


# -- Accounting --
@router.get("/accounting/monthly")
def api_get_monthly_accounting(year_month: str):
    from backend.modules.accounting import get_monthly_accounting
    return get_monthly_accounting(store, year_month)


@router.post("/accounting/fixed-costs")
def api_save_fixed_costs(data: dict):
    from backend.data.models import MonthlyFixedCost
    cost = MonthlyFixedCost(
        month=data["month"],
        rent=data.get("rent", 0),
        utilities=data.get("utilities", 0),
        other=data.get("other", 0),
    )
    store.save_monthly_cost(cost)
    return {"ok": True}


@router.get("/accounting/fixed-costs")
def api_get_fixed_costs(month: str):
    cost = store.get_monthly_cost(month)
    if cost:
        return cost.model_dump()
    return {"month": month, "rent": 0, "utilities": 0, "other": 0}


@router.post("/accounting/income")
def api_add_income(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.accounting import record_income
    record_income(store, data["date"], data["income"])
    return {"ok": True}


@router.post("/accounting/delete-platform")
def api_delete_platform(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.accounting import delete_platform_entry
    delete_platform_entry(store, data["type"], data["date"], data["platform"])
    return {"ok": True}


@router.post("/accounting/expense")
def api_add_expense(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.accounting import record_expense
    record_expense(store, data["date"], data["expense"])
    return {"ok": True}


@router.get("/accounting/daily")
def api_get_daily_accounting(date: str):
    from backend.modules.accounting import get_daily_accounting
    return get_daily_accounting(store, date)


@router.get("/revenue")
def api_get_revenue(date: str):
    from backend.modules.accounting import get_daily_revenue
    return get_daily_revenue(store, date)


@router.post("/revenue")
def api_add_revenue(data: dict, user_id: str = Depends(get_current_user)):
    from backend.modules.accounting import record_platform_revenue
    record_platform_revenue(store, data["date"], data["revenues"])
    return {"ok": True}


@router.get("/profit")
def api_get_profit(date: str):
    from backend.modules.daily_report import calculate_daily_profit
    report = calculate_daily_profit(store, date)
    return report.model_dump()


# -- Pricing --
@router.get("/pricing/analysis")
def api_pricing(monthly_rent: float = 5000, monthly_labor: float = 15000, total_items: int = 5000, sales_volumes: str = ""):
    vols = {}
    for pair in sales_volumes.split(","):
        if ":" in pair:
            k, v = pair.split(":")
            vols[k.strip()] = int(v.strip())
    return analyze_all_items(store, monthly_rent, monthly_labor, total_items, vols)


# -- Payroll --
@router.get("/payroll")
def api_payroll(year_month: str):
    return generate_monthly_payroll(store, year_month)


# -- Chat (simulates Feishu Bot locally) --
@router.get("/chat")
def api_chat(text: str):
    from backend.bot.nlu import parse_intent, Intent
    parsed = parse_intent(text)
    return {"intent": parsed.intent.name, "params": parsed.params, "raw": text}


# Auto-seed on first import
if not store.list_staff():
    from backend.seed import seed
    seed(store)
