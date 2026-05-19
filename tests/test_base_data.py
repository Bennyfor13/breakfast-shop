from backend.data.models import Staff, Role, MenuItem, Ingredient
from backend.modules.base_data import (
    create_staff, update_staff, remove_staff, list_active_staff,
    create_menu_item, update_menu_item, remove_menu_item, list_active_menu,
    get_bom_for_item,
)


def test_create_and_list_staff(store):
    create_staff(store, "t1", "赵六", [Role.KITCHEN], morning_rate=90, evening_rate=70, note="新员工")
    staff = store.get_staff("t1")
    assert staff.name == "赵六"
    assert staff.roles == [Role.KITCHEN]
    assert staff.morning_rate == 90
    staff_list = list_active_staff(store)
    assert len(staff_list) == 4  # 3 seeded + 1 new


def test_remove_staff_soft_delete(store):
    remove_staff(store, "s1")
    assert store.get_staff("s1").active is False
    active = list_active_staff(store)
    assert all(s.id != "s1" for s in active)


def test_update_staff(store):
    update_staff(store, "s1", name="张三丰", roles=[Role.KITCHEN, Role.SERVICE])
    updated = store.get_staff("s1")
    assert updated.name == "张三丰"
    assert Role.SERVICE in updated.roles


def test_create_menu_with_bom(store):
    create_menu_item(store, "m3", "馄饨", 5.0, [
        Ingredient(name="面粉", amount=50),
        Ingredient(name="猪肉", amount=30),
    ])
    item = store.get_menu_item("m3")
    assert item.name == "馄饨"
    assert len(item.bom) == 2
    assert item.bom[0].name == "面粉"


def test_get_bom_for_item(store):
    bom = get_bom_for_item(store, "m1")
    assert len(bom) == 4
    names = [i.name for i in bom]
    assert "中筋面粉" in names


def test_remove_menu_soft_delete(store):
    remove_menu_item(store, "m1")
    assert store.get_menu_item("m1").active is False
    active = list_active_menu(store)
    assert all(m.id != "m1" for m in active)
