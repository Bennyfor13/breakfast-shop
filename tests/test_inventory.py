import pytest
from backend.data.models import IngredientStock
from backend.modules.inventory import (
    forecast_ingredient_needs, generate_purchase_list,
    apply_waste_feedback, INGREDIENT_CATEGORIES,
)


def test_forecast_ingredient_needs(store):
    predicted_sales = {"m1": 100, "m2": 50}
    needs = forecast_ingredient_needs(store, predicted_sales)
    assert needs["中筋面粉"] == pytest.approx(8000, rel=0.01)   # 80g * 100
    assert needs["猪前腿肉"] == pytest.approx(4500, rel=0.01)   # 45g * 100
    assert needs["黄豆"] == pytest.approx(1500, rel=0.01)        # 30g * 50


def test_forecast_merges_shared_ingredients(store):
    from backend.data.models import MenuItem, Ingredient
    store.menu["m3"] = MenuItem(
        id="m3", name="猪肉面", price=8.0,
        bom=[Ingredient(name="猪前腿肉", amount=100), Ingredient(name="面条", amount=150)]
    )
    predicted_sales = {"m1": 100, "m3": 50}
    needs = forecast_ingredient_needs(store, predicted_sales)
    # 猪肉: 45g*100 + 100g*50 = 4500 + 5000 = 9500
    assert needs["猪前腿肉"] == pytest.approx(9500, rel=0.01)


def test_generate_purchase_list_with_stock(store):
    store.set_stock(IngredientStock(name="中筋面粉", current=2000, unit="g", category="干货"))
    store.set_stock(IngredientStock(name="猪前腿肉", current=500, unit="g", category="鲜食"))
    needs = {"中筋面粉": 8000, "猪前腿肉": 4500, "葱": 500}
    purchases = generate_purchase_list(store, needs)
    # 面粉: 8000-2000 = 6000, no buffer for 干货
    assert purchases["中筋面粉"] == 6000
    # 猪肉: 4500-500 = 4000, +10% buffer for 鲜食 = 4400
    assert purchases["猪前腿肉"] == pytest.approx(4400, rel=0.01)


def test_apply_waste_feedback(store):
    from backend.data.models import WasteFeedback
    feedback = WasteFeedback(
        date="2026-05-19",
        over_prepared={"中筋面粉": 2000},
        under_prepared={},
    )
    store.save_waste(feedback)
    needs = {"中筋面粉": 8000}
    adjusted = apply_waste_feedback(store, needs)
    # 2000/8000 = 25% over, damped correction: 25% * 0.5 = 12.5% → 8000 * 0.875 = 7000
    assert adjusted["中筋面粉"] == pytest.approx(7000, rel=0.01)


def test_ingredient_category_buffer():
    assert INGREDIENT_CATEGORIES["鲜食"] == 0.10
    assert INGREDIENT_CATEGORIES["半鲜"] == 0.20
    assert INGREDIENT_CATEGORIES["干货"] == 0.0
