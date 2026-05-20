from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from backend.data.mock_store import MockStore
from backend.data.models import (
    Staff, Role, MenuItem, Ingredient, DemandTemplate,
    AttendanceLog, PerformanceScore, IngredientStock, WasteFeedback,
)
from backend.modules.base_data import (
    create_staff, list_active_staff, update_staff, remove_staff,
    create_menu_item, list_active_menu, get_bom_for_item, remove_menu_item,
)
from backend.modules.scheduling import (
    generate_weekly_schedule, find_replacement,
    edit_shift, assign_replacement,
)
from backend.modules.inventory import (
    forecast_ingredient_needs, generate_purchase_list,
)
from backend.modules.pricing import analyze_all_items
from backend.modules.payroll import generate_monthly_payroll

router = APIRouter(prefix="/api")
store = MockStore()


# -- Staff --
@router.get("/staff")
def api_list_staff():
    return [s.model_dump() for s in list_active_staff(store)]


@router.post("/staff")
def api_create_staff(name: str, roles: list[str] = Query(...), morning_rate: float = 80, evening_rate: float = 60, note: str = ""):
    role_enums = [Role(r) for r in roles]
    staff = create_staff(store, None, name, role_enums, morning_rate, evening_rate, note)
    return staff.model_dump()


@router.put("/staff/{staff_id}")
def api_update_staff(staff_id: str, data: dict):
    result = update_staff(store, staff_id, **data)
    if not result:
        raise HTTPException(404)
    return result.model_dump()


@router.delete("/staff/{staff_id}")
def api_delete_staff(staff_id: str):
    remove_staff(store, staff_id)
    return {"ok": True}


# -- Menu --
@router.get("/menu")
def api_list_menu():
    return [m.model_dump() for m in list_active_menu(store)]


@router.post("/menu")
def api_create_menu(name: str, price: float, bom: list[dict] = []):
    ingredients = [Ingredient(**i) for i in bom]
    item = create_menu_item(store, None, name, price, ingredients)
    return item.model_dump()


@router.get("/menu/{item_id}/bom")
def api_get_bom(item_id: str):
    return [i.model_dump() for i in get_bom_for_item(store, item_id)]


@router.delete("/menu/{item_id}")
def api_delete_menu(item_id: str):
    remove_menu_item(store, item_id)
    return {"ok": True}


# -- Demand Template --
@router.get("/demand-template")
def api_get_demand():
    return store.get_demand_template().model_dump()


@router.put("/demand-template")
def api_set_demand(data: dict):
    template = DemandTemplate(entries=data.get("entries", {}))
    store.set_demand_template(template)
    return {"ok": True}


# -- Schedule --
@router.get("/schedule")
def api_get_schedule(week_start: str, boss_absent: str = ""):
    absent = set(boss_absent.split(",")) if boss_absent else set()
    schedule = generate_weekly_schedule(store, week_start, absent)
    store.save_shifts(schedule.shifts)
    return schedule.model_dump()


@router.get("/schedule/replacement")
def api_find_replacement(absent_id: str, date: str):
    existing = store.get_shifts_by_date(date)
    candidates = find_replacement(store, absent_id, existing, date)
    return [c.model_dump() for c in candidates]


@router.post("/schedule/edit")
def api_edit_shift(data: dict):
    success = edit_shift(
        store, data["date"], data["period"],
        data["old_staff_id"], data["new_staff_id"],
    )
    if not success:
        raise HTTPException(404, "Shift not found")
    return {"ok": True}


@router.post("/schedule/assign-replacement")
def api_assign_replacement(data: dict):
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
def api_save_waste(data: dict):
    fb = WasteFeedback(**data)
    store.save_waste(fb)
    return {"ok": True}


# -- Attendance --
@router.post("/attendance")
def api_save_attendance(data: dict):
    log = AttendanceLog(**data)
    store.save_attendance(log)
    return {"ok": True}


# -- Performance --
@router.post("/performance")
def api_save_performance(data: dict):
    score = PerformanceScore(**data)
    store.save_performance(score)
    return {"ok": True}


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
