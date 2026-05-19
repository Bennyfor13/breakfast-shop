from __future__ import annotations
from backend.data.interface import AbstractStore

ALL_QUADRANTS = ["明星", "金牛", "引流款", "考虑砍掉"]

DEFAULT_INGREDIENT_PRICES: dict[str, float] = {
    "中筋面粉": 0.006,   # Y6/kg
    "猪前腿肉": 0.04,    # Y40/kg
    "葱": 0.01,
    "酱油": 0.02,
    "黄豆": 0.02,
    "面粉": 0.006,
    "猪肉": 0.04,
    "面条": 0.008,
    "盐": 0.005,
    "香油": 0.03,
    "姜": 0.015,
}


def calculate_item_cost(
    store: AbstractStore, item_id: str,
    monthly_rent: float, monthly_labor: float, total_items_per_month: int,
) -> dict:
    item = store.get_menu_item(item_id)
    if not item:
        return {}

    raw_cost = sum(
        ing.amount * DEFAULT_INGREDIENT_PRICES.get(ing.name, 0.01)
        for ing in item.bom
    )
    rent_per_item = monthly_rent / max(total_items_per_month, 1)
    labor_per_item = monthly_labor / max(total_items_per_month, 1)

    raw = round(raw_cost, 2)
    rent = round(rent_per_item, 2)
    labor = round(labor_per_item, 2)
    return {
        "item_name": item.name,
        "raw_material": raw,
        "rent_per_item": rent,
        "labor_per_item": labor,
        "total": round(raw + rent + labor, 2),
    }


def item_profit_margin(
    store: AbstractStore, item_id: str,
    monthly_rent: float, monthly_labor: float, total_items_per_month: int,
) -> dict:
    item = store.get_menu_item(item_id)
    cost = calculate_item_cost(store, item_id, monthly_rent, monthly_labor, total_items_per_month)
    if not cost:
        return {}
    gross = item.price - cost["total"]
    return {
        "item_name": item.name,
        "selling_price": item.price,
        "total_cost": cost["total"],
        "gross_profit": round(gross, 2),
        "margin_pct": round(gross / item.price * 100, 1) if item.price > 0 else 0,
    }


def quadrant_classify(
    store: AbstractStore, item_id: str, margin_pct: float,
    sales_volume: int, avg_volume: float,
) -> str:
    high_margin = margin_pct >= 30
    high_volume = sales_volume >= avg_volume

    if high_margin and high_volume:
        return "明星"
    elif high_margin and not high_volume:
        return "金牛"
    elif not high_margin and high_volume:
        return "引流款"
    else:
        return "考虑砍掉"


def analyze_all_items(
    store: AbstractStore, monthly_rent: float, monthly_labor: float,
    total_items_per_month: int, sales_volumes: dict[str, int],
) -> list[dict]:
    items = store.list_menu()
    if not items:
        return []
    avg_vol = sum(sales_volumes.values()) / max(len(sales_volumes), 1)
    results = []
    for item in items:
        margin = item_profit_margin(
            store, item.id, monthly_rent, monthly_labor, total_items_per_month,
        )
        vol = sales_volumes.get(item.id, 0)
        quadrant = quadrant_classify(store, item.id, margin.get("margin_pct", 0), vol, avg_vol)
        results.append({**margin, "sales_volume": vol, "quadrant": quadrant})
    return sorted(results, key=lambda r: r.get("margin_pct", 0), reverse=True)
