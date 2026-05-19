from __future__ import annotations
import uuid
from backend.data.interface import AbstractStore
from backend.data.models import Staff, Role, MenuItem, Ingredient


def create_staff(
    store: AbstractStore, staff_id: str | None, name: str, roles: list[Role],
    morning_rate: float = 80.0, evening_rate: float = 60.0, note: str = "",
) -> Staff:
    sid = staff_id or str(uuid.uuid4())[:8]
    staff = Staff(id=sid, name=name, roles=roles,
                  morning_rate=morning_rate, evening_rate=evening_rate, note=note)
    store.add_staff(staff)
    return staff


def list_active_staff(store: AbstractStore) -> list[Staff]:
    return store.list_staff()


def update_staff(store: AbstractStore, staff_id: str, **kwargs) -> Staff | None:
    staff = store.get_staff(staff_id)
    if not staff:
        return None
    for k, v in kwargs.items():
        if hasattr(staff, k):
            setattr(staff, k, v)
    store.update_staff(staff)
    return staff


def remove_staff(store: AbstractStore, staff_id: str) -> None:
    store.delete_staff(staff_id)


def create_menu_item(
    store: AbstractStore, item_id: str | None, name: str, price: float,
    bom: list[Ingredient],
) -> MenuItem:
    mid = item_id or str(uuid.uuid4())[:8]
    item = MenuItem(id=mid, name=name, price=price, bom=bom)
    store.add_menu_item(item)
    return item


def list_active_menu(store: AbstractStore) -> list[MenuItem]:
    return store.list_menu()


def get_bom_for_item(store: AbstractStore, item_id: str) -> list[Ingredient]:
    item = store.get_menu_item(item_id)
    if not item:
        return []
    return item.bom


def update_menu_item(store: AbstractStore, item_id: str, **kwargs) -> MenuItem | None:
    item = store.get_menu_item(item_id)
    if not item:
        return None
    for k, v in kwargs.items():
        if hasattr(item, k):
            setattr(item, k, v)
    store.update_menu_item(item)
    return item


def remove_menu_item(store: AbstractStore, item_id: str) -> None:
    store.delete_menu_item(item_id)
