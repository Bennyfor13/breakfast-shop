from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Role(str, Enum):
    KITCHEN = "后厨"
    SERVICE = "传菜"
    CASHIER = "收银"


class Staff(BaseModel):
    id: str
    name: str
    roles: list[Role]
    note: str = ""
    morning_rate: float = 80.0
    evening_rate: float = 60.0
    active: bool = True


class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str = "g"


class MenuItem(BaseModel):
    id: str
    name: str
    price: float
    bom: list[Ingredient] = Field(default_factory=list)
    active: bool = True


class DemandTemplate(BaseModel):
    """Boss fills this once per Phase 1. Key: "Monday-early", value: staff needed per role."""
    entries: dict[str, dict[str, int]] = Field(default_factory=dict)
    # e.g. {"Monday-early": {"后厨": 2, "传菜": 1, "收银": 1}}


class Shift(BaseModel):
    staff_id: str
    date: str       # "2026-05-20"
    period: str     # "早班" | "晚班"
    role: Role


class Schedule(BaseModel):
    week_start: str  # "2026-05-18"
    shifts: list[Shift]


class AttendanceLog(BaseModel):
    """Boss marks exceptions daily. schedule = default attendance."""
    date: str
    absent: list[str] = Field(default_factory=list)     # staff_ids who didn't show
    substitute: dict[str, str] = Field(default_factory=dict)  # absent_id → replacement_id
    overtime: list[str] = Field(default_factory=list)   # staff_ids who worked extra shift
    notes: str = ""


class PerformanceScore(BaseModel):
    staff_id: str
    date: str | None = None  # None = monthly score
    score: float  # 1-5


class IngredientStock(BaseModel):
    name: str
    current: float
    unit: str = "g"
    category: str = "干货"  # "鲜食" | "半鲜" | "干货"


class SalesRecord(BaseModel):
    date: str
    hour: int
    item_id: str
    quantity: int
    revenue: float


class WasteFeedback(BaseModel):
    date: str
    over_prepared: dict[str, float] = Field(default_factory=dict)
    under_prepared: dict[str, float] = Field(default_factory=dict)
