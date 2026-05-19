import pytest
from backend.modules.pricing import (
    calculate_item_cost, item_profit_margin, quadrant_classify, ALL_QUADRANTS,
)


def test_calculate_item_cost(store):
    cost = calculate_item_cost(store, "m1", monthly_rent=5000, monthly_labor=15000, total_items_per_month=5000)
    assert cost["raw_material"] > 0
    assert cost["rent_per_item"] == 1.0
    assert cost["labor_per_item"] == 3.0
    assert cost["total"] == pytest.approx(cost["raw_material"] + 1.0 + 3.0)


def test_item_profit_margin(store):
    margin = item_profit_margin(store, "m1", monthly_rent=5000, monthly_labor=15000, total_items_per_month=5000)
    assert margin["selling_price"] == 3.0
    assert margin["total_cost"] > 0
    assert margin["gross_profit"] == pytest.approx(3.0 - margin["total_cost"])
    assert margin["margin_pct"] < 0  # m1 costs more to make than it sells for at these rates


def test_quadrant_classify_high_volume_high_margin(store):
    result = quadrant_classify(store, "m1", margin_pct=57, sales_volume=3000, avg_volume=1000)
    assert result == "明星"


def test_quadrant_classify_low_volume_low_margin(store):
    result = quadrant_classify(store, "m1", margin_pct=5, sales_volume=200, avg_volume=1000)
    assert result == "考虑砍掉"


def test_quadrant_classify_high_margin_low_volume(store):
    result = quadrant_classify(store, "m1", margin_pct=60, sales_volume=200, avg_volume=1000)
    assert result == "金牛"


def test_quadrant_classify_low_margin_high_volume(store):
    result = quadrant_classify(store, "m1", margin_pct=10, sales_volume=3000, avg_volume=1000)
    assert result == "引流款"
