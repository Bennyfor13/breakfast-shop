from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import IngredientStock

INGREDIENT_CATEGORIES = {"鲜食": 0.10, "半鲜": 0.20, "干货": 0.0}


def _get_category(store: AbstractStore, ingredient_name: str) -> str:
    stock = store.get_stock(ingredient_name)
    return stock.category if stock else "干货"


def forecast_ingredient_needs(
    store: AbstractStore, predicted_sales: dict[str, int],
) -> dict[str, float]:
    """predicted_sales: {menu_item_id: quantity}. Returns {ingredient_name: total_amount}."""
    totals: dict[str, float] = {}
    for item_id, qty in predicted_sales.items():
        item = store.get_menu_item(item_id)
        if not item:
            continue
        for ing in item.bom:
            totals[ing.name] = totals.get(ing.name, 0) + ing.amount * qty
    return totals


def generate_purchase_list(
    store: AbstractStore, needs: dict[str, float],
) -> dict[str, float]:
    """Subtract current stock, add category-appropriate buffer."""
    purchases: dict[str, float] = {}
    for name, need in needs.items():
        stock = store.get_stock(name)
        current = stock.current if stock else 0
        gap = need - current
        if gap <= 0:
            continue
        cat = _get_category(store, name)
        buffer = INGREDIENT_CATEGORIES.get(cat, 0.10)
        purchases[name] = round(gap * (1 + buffer), 1)
    return purchases


def apply_waste_feedback(
    store: AbstractStore, needs: dict[str, float],
) -> dict[str, float]:
    """Look at recent waste feedback and adjust needs proportionally."""
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    feedbacks = store.get_waste(week_ago, today)
    if not feedbacks:
        return needs

    adjusted = dict(needs)
    for name in list(adjusted.keys()):
        for fb in feedbacks:
            if name in fb.over_prepared and needs.get(name, 0) > 0:
                over_ratio = fb.over_prepared[name] / needs[name]
                if over_ratio > 0.05:
                    adjusted[name] *= (1 - over_ratio * 0.5)
            if name in fb.under_prepared and needs.get(name, 0) > 0:
                under_ratio = fb.under_prepared[name] / needs[name]
                if under_ratio > 0.05:
                    adjusted[name] *= (1 + under_ratio * 0.5)

    return {k: round(v, 1) for k, v in adjusted.items()}
