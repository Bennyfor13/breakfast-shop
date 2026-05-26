from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import DailyProfitReport, ActualConsumption
from backend.modules.accounting import get_daily_revenue


def get_ingredient_consumption(
    store: AbstractStore,
    date: str
) -> dict[str, float]:
    """计算某日理论原料消耗"""
    sales = store.get_sales(date, date)
    consumption = {}

    for sale in sales:
        item = store.get_menu_item(sale.item_id)
        if not item:
            continue
        for ing in item.bom:
            consumption[ing.name] = consumption.get(ing.name, 0) + ing.amount * sale.quantity

    return consumption


def record_actual_consumption(
    store: AbstractStore,
    date: str,
    actual: dict[str, float]
) -> dict:
    """记录实际原料消耗，并计算与理论值的差异"""
    theoretical = get_ingredient_consumption(store, date)
    differences = []

    for name, actual_val in actual.items():
        theo_val = theoretical.get(name, 0)
        diff = actual_val - theo_val
        pct = (diff / theo_val * 100) if theo_val > 0 else 0

        consumption = ActualConsumption(
            date=date,
            ingredient_name=name,
            theoretical=theo_val,
            actual=actual_val,
            difference=diff
        )
        store.save_actual_consumption(consumption)

        differences.append({
            "ingredient": name,
            "theoretical": theo_val,
            "actual": actual_val,
            "difference": diff,
            "percentage": round(pct, 1)
        })

    return {"date": date, "differences": differences}


def calculate_daily_profit(
    store: AbstractStore,
    date: str
) -> DailyProfitReport:
    """计算某日利润"""
    from datetime import datetime
    from backend.modules.pricing import DEFAULT_INGREDIENT_PRICES

    revenue_data = get_daily_revenue(store, date)
    total_revenue = revenue_data["total"]

    sales = store.get_sales(date, date)

    raw_cost = 0
    item_breakdown = []

    for sale in sales:
        item = store.get_menu_item(sale.item_id)
        if not item:
            continue

        item_raw_cost = sum(
            ing.amount * DEFAULT_INGREDIENT_PRICES.get(ing.name, 0.01)
            for ing in item.bom
        ) * sale.quantity

        raw_cost += item_raw_cost
        item_profit = sale.revenue - item_raw_cost

        item_breakdown.append({
            "item": item.name,
            "sold": sale.quantity,
            "revenue": sale.revenue,
            "cost": round(item_raw_cost, 2),
            "profit": round(item_profit, 2)
        })

    shifts = store.get_shifts_by_date(date)
    labor_cost = len(shifts) * 80

    month = date[:7]
    monthly_cost = store.get_monthly_cost(month)
    fixed_cost = monthly_cost.daily_cost() if monthly_cost else 100

    total_cost = raw_cost + labor_cost + fixed_cost
    net_profit = total_revenue - total_cost

    return DailyProfitReport(
        date=date,
        total_revenue=total_revenue,
        total_cost=round(total_cost, 2),
        net_profit=round(net_profit, 2),
        item_breakdown=item_breakdown,
        ingredient_consumption=get_ingredient_consumption(store, date)
    )
