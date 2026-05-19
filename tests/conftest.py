import pytest
from backend.data.mock_store import MockStore


@pytest.fixture
def store():
    s = MockStore()
    from backend.data.models import (
        Staff, Role, MenuItem, Ingredient, DemandTemplate
    )
    s.staff["s1"] = Staff(
        id="s1", name="张三", roles=[Role.KITCHEN],
        morning_rate=80, evening_rate=60
    )
    s.staff["s2"] = Staff(
        id="s2", name="李四", roles=[Role.SERVICE, Role.CASHIER],
        morning_rate=70, evening_rate=50
    )
    s.staff["s3"] = Staff(
        id="s3", name="王五", roles=[Role.KITCHEN],
        morning_rate=80, evening_rate=60
    )
    s.menu["m1"] = MenuItem(
        id="m1", name="鲜肉包", price=3.0,
        bom=[
            Ingredient(name="中筋面粉", amount=80),
            Ingredient(name="猪前腿肉", amount=45),
            Ingredient(name="葱", amount=5),
            Ingredient(name="酱油", amount=3, unit="ml"),
        ]
    )
    s.menu["m2"] = MenuItem(
        id="m2", name="豆浆", price=2.0,
        bom=[Ingredient(name="黄豆", amount=30)]
    )
    s.demand_template.entries = {
        "Monday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Monday-late": {"后厨": 1, "传菜": 1, "收银": 0},
    }
    return s
