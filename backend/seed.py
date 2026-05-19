"""Seed the mock store with realistic demo data."""
from backend.data.mock_store import MockStore
from backend.data.models import (
    Staff, Role, MenuItem, Ingredient, DemandTemplate,
    IngredientStock,
)


def seed(s: MockStore):
    # Staff
    s.add_staff(Staff(id="s1", name="张三", roles=[Role.KITCHEN],
                      morning_rate=80, evening_rate=60, note="老师傅，拿手包子"))
    s.add_staff(Staff(id="s2", name="李四", roles=[Role.KITCHEN],
                      morning_rate=80, evening_rate=60, note="会炒锅和切配"))
    s.add_staff(Staff(id="s3", name="王五", roles=[Role.SERVICE, Role.CASHIER],
                      morning_rate=70, evening_rate=50))
    s.add_staff(Staff(id="s4", name="赵六", roles=[Role.SERVICE],
                      morning_rate=60, evening_rate=45, note="新人"))
    s.add_staff(Staff(id="s5", name="钱七", roles=[Role.CASHIER],
                      morning_rate=70, evening_rate=50))

    # Menu with BOMs
    s.add_menu_item(MenuItem(id="m1", name="鲜肉包", price=3.0, bom=[
        Ingredient(name="中筋面粉", amount=80), Ingredient(name="猪前腿肉", amount=45),
        Ingredient(name="葱", amount=5), Ingredient(name="姜", amount=2),
        Ingredient(name="酱油", amount=3, unit="ml"), Ingredient(name="盐", amount=0.5),
        Ingredient(name="香油", amount=1, unit="ml"),
    ]))
    s.add_menu_item(MenuItem(id="m2", name="豆浆", price=2.0, bom=[
        Ingredient(name="黄豆", amount=30), Ingredient(name="白糖", amount=5),
    ]))
    s.add_menu_item(MenuItem(id="m3", name="油条", price=1.5, bom=[
        Ingredient(name="中筋面粉", amount=60), Ingredient(name="油", amount=10, unit="ml"),
        Ingredient(name="盐", amount=1),
    ]))
    s.add_menu_item(MenuItem(id="m4", name="茶叶蛋", price=1.5, bom=[
        Ingredient(name="鸡蛋", amount=60), Ingredient(name="茶叶", amount=2),
        Ingredient(name="酱油", amount=5, unit="ml"),
    ]))
    s.add_menu_item(MenuItem(id="m5", name="馄饨", price=5.0, bom=[
        Ingredient(name="中筋面粉", amount=50), Ingredient(name="猪前腿肉", amount=30),
        Ingredient(name="葱", amount=3), Ingredient(name="紫菜", amount=2),
    ]))

    # Demand template
    s.set_demand_template(DemandTemplate(entries={
        "Monday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Monday-late": {"后厨": 1, "传菜": 1, "收银": 0},
        "Tuesday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Tuesday-late": {"后厨": 1, "传菜": 1, "收银": 0},
        "Wednesday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Wednesday-late": {"后厨": 1, "传菜": 1, "收银": 0},
        "Thursday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Thursday-late": {"后厨": 1, "传菜": 1, "收银": 0},
        "Friday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Friday-late": {"后厨": 1, "传菜": 1, "收银": 0},
        "Saturday-early": {"后厨": 2, "传菜": 1, "收银": 1},
        "Saturday-late": {"后厨": 1, "传菜": 1, "收银": 1},
        "Sunday-early": {"后厨": 1, "传菜": 1, "收银": 1},
        "Sunday-late": {"后厨": 1, "传菜": 0, "收银": 0},
    }))

    # Initial stock
    stocks = [
        ("中筋面粉", 10000, "g", "干货"), ("猪前腿肉", 5000, "g", "鲜食"),
        ("葱", 1000, "g", "鲜食"), ("姜", 500, "g", "干货"),
        ("酱油", 2000, "ml", "干货"), ("盐", 3000, "g", "干货"),
        ("香油", 1000, "ml", "干货"), ("黄豆", 3000, "g", "干货"),
        ("白糖", 2000, "g", "干货"), ("鸡蛋", 3000, "g", "半鲜"),
        ("茶叶", 500, "g", "干货"), ("紫菜", 500, "g", "干货"),
        ("油", 5000, "ml", "干货"),
    ]
    for name, qty, unit, cat in stocks:
        s.set_stock(IngredientStock(name=name, current=qty, unit=unit, category=cat))

    print(f"Seeded: {len(s.list_staff())} staff, {len(s.list_menu())} menu items")


if __name__ == "__main__":
    from backend.api.routes import store
    seed(store)
