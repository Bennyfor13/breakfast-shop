from __future__ import annotations
import json
from pathlib import Path
from backend.data.interface import AbstractStore
from backend.data.models import (
    Staff, MenuItem, DemandTemplate, Shift, AttendanceLog,
    PerformanceScore, IngredientStock, SalesRecord, WasteFeedback,
    PlatformRevenue, ActualConsumption, MonthlyFixedCost,
    DailyIncome, DailyExpense,
)


_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "store_data.json"


def _models_to_dict(data: dict | list) -> dict | list:
    """Convert a collection of BaseModels to serializable dicts."""
    if isinstance(data, dict):
        return {k: v.model_dump() for k, v in data.items()}
    return [v.model_dump() for v in data]


def _dict_to_models(data: dict | list, model_cls, is_dict=False) -> dict | list:
    """Restore a collection of BaseModels from dicts."""
    if is_dict and isinstance(data, dict):
        return {k: model_cls.model_validate(v) for k, v in data.items()}
    if isinstance(data, list):
        return [model_cls.model_validate(v) for v in data]
    return {}


class MockStore(AbstractStore):
    def __init__(self):
        self.staff: dict[str, Staff] = {}
        self.menu: dict[str, MenuItem] = {}
        self.demand_template = DemandTemplate()
        self.shifts: list[Shift] = []
        self.attendance: dict[str, AttendanceLog] = {}
        self.performance: list[PerformanceScore] = []
        self.stocks: dict[str, IngredientStock] = {}
        self.sales: list[SalesRecord] = []
        self.waste: list[WasteFeedback] = []
        self.platform_revenues: list[PlatformRevenue] = []
        self.actual_consumptions: list[ActualConsumption] = []
        self.monthly_costs: dict[str, MonthlyFixedCost] = {}
        self.daily_income: dict[str, DailyIncome] = {}
        self.daily_expense: dict[str, DailyExpense] = {}

    @classmethod
    def load_or_create(cls) -> MockStore:
        """Load from disk if exists, otherwise create empty store."""
        store = cls()
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
                store.staff = _dict_to_models(raw.get("staff", {}), Staff, is_dict=True)
                store.menu = _dict_to_models(raw.get("menu", {}), MenuItem, is_dict=True)
                if raw.get("demand_template"):
                    store.demand_template = DemandTemplate.model_validate(raw["demand_template"])
                store.shifts = _dict_to_models(raw.get("shifts", []), Shift)
                store.attendance = _dict_to_models(raw.get("attendance", {}), AttendanceLog, is_dict=True)
                store.performance = _dict_to_models(raw.get("performance", []), PerformanceScore)
                store.stocks = _dict_to_models(raw.get("stocks", {}), IngredientStock, is_dict=True)
                store.sales = _dict_to_models(raw.get("sales", []), SalesRecord)
                store.waste = _dict_to_models(raw.get("waste", []), WasteFeedback)
                store.platform_revenues = _dict_to_models(raw.get("platform_revenues", []), PlatformRevenue)
                store.actual_consumptions = _dict_to_models(raw.get("actual_consumptions", []), ActualConsumption)
                store.monthly_costs = _dict_to_models(raw.get("monthly_costs", {}), MonthlyFixedCost, is_dict=True)
                store.daily_income = _dict_to_models(raw.get("daily_income", {}), DailyIncome, is_dict=True)
                store.daily_expense = _dict_to_models(raw.get("daily_expense", {}), DailyExpense, is_dict=True)
            except Exception as e:
                print(f"Failed to load data file, starting fresh: {e}")
        return store

    def _save(self) -> None:
        """Persist all data to JSON file."""
        raw = {
            "staff": _models_to_dict(self.staff),
            "menu": _models_to_dict(self.menu),
            "demand_template": self.demand_template.model_dump(),
            "shifts": _models_to_dict(self.shifts),
            "attendance": _models_to_dict(self.attendance),
            "performance": _models_to_dict(self.performance),
            "stocks": _models_to_dict(self.stocks),
            "sales": _models_to_dict(self.sales),
            "waste": _models_to_dict(self.waste),
            "platform_revenues": _models_to_dict(self.platform_revenues),
            "actual_consumptions": _models_to_dict(self.actual_consumptions),
            "monthly_costs": _models_to_dict(self.monthly_costs),
            "daily_income": _models_to_dict(self.daily_income),
            "daily_expense": _models_to_dict(self.daily_expense),
        }
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DATA_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_staff(self) -> list[Staff]:
        return [s for s in self.staff.values() if s.active]

    def get_staff(self, staff_id: str) -> Staff | None:
        return self.staff.get(staff_id)

    def add_staff(self, staff: Staff) -> None:
        self.staff[staff.id] = staff
        self._save()

    def update_staff(self, staff: Staff) -> None:
        if staff.id in self.staff:
            self.staff[staff.id] = staff
            self._save()

    def delete_staff(self, staff_id: str) -> None:
        s = self.staff.get(staff_id)
        if s:
            s.active = False
            self._save()

    def list_menu(self) -> list[MenuItem]:
        return [m for m in self.menu.values() if m.active]

    def get_menu_item(self, item_id: str) -> MenuItem | None:
        return self.menu.get(item_id)

    def add_menu_item(self, item: MenuItem) -> None:
        self.menu[item.id] = item
        self._save()

    def update_menu_item(self, item: MenuItem) -> None:
        if item.id in self.menu:
            self.menu[item.id] = item
            self._save()

    def delete_menu_item(self, item_id: str) -> None:
        m = self.menu.get(item_id)
        if m:
            m.active = False
            self._save()

    def get_demand_template(self) -> DemandTemplate:
        return self.demand_template

    def set_demand_template(self, template: DemandTemplate) -> None:
        self.demand_template = template
        self._save()

    def save_shifts(self, shifts: list[Shift]) -> None:
        if not shifts:
            return
        # Derive Monday of the week from the first shift's date
        from datetime import datetime, timedelta
        dt = datetime.strptime(shifts[0].date, "%Y-%m-%d")
        monday = dt - timedelta(days=dt.weekday())
        week = monday.strftime("%Y-%m-%d")
        end = _add_week(week)
        self.shifts = [s for s in self.shifts if s.date < week or s.date >= end] + shifts
        self._save()

    def get_shifts(self, week_start: str) -> list[Shift]:
        end = _add_week(week_start)
        return [s for s in self.shifts if week_start <= s.date < end]

    def get_shifts_by_date(self, date: str) -> list[Shift]:
        return [s for s in self.shifts if s.date == date]

    def save_attendance(self, log: AttendanceLog) -> None:
        self.attendance[log.date] = log
        self._save()

    def get_attendance(self, date: str) -> AttendanceLog | None:
        return self.attendance.get(date)

    def list_attendance(self, from_date: str, to_date: str) -> list[AttendanceLog]:
        return [a for d, a in self.attendance.items() if from_date <= d <= to_date]

    def save_performance(self, score: PerformanceScore) -> None:
        self.performance.append(score)
        self._save()

    def get_performance(self, staff_id: str, from_date: str, to_date: str) -> list[PerformanceScore]:
        return [
            p for p in self.performance
            if p.staff_id == staff_id
            and (p.date is None or from_date <= p.date <= to_date)
        ]

    def list_stocks(self) -> list[IngredientStock]:
        return list(self.stocks.values())

    def get_stock(self, name: str) -> IngredientStock | None:
        return self.stocks.get(name)

    def set_stock(self, stock: IngredientStock) -> None:
        self.stocks[stock.name] = stock
        self._save()

    def add_sales(self, records: list[SalesRecord]) -> None:
        self.sales.extend(records)
        self._save()

    def get_sales(self, from_date: str, to_date: str) -> list[SalesRecord]:
        return [r for r in self.sales if from_date <= r.date <= to_date]

    def save_waste(self, feedback: WasteFeedback) -> None:
        self.waste = [w for w in self.waste if w.date != feedback.date]
        self.waste.append(feedback)
        self._save()

    def get_waste(self, from_date: str, to_date: str) -> list[WasteFeedback]:
        return [w for w in self.waste if from_date <= w.date <= to_date]

    def save_platform_revenue(self, revenue: PlatformRevenue) -> None:
        self.platform_revenues.append(revenue)
        self._save()

    def get_platform_revenues(self, date: str) -> list[PlatformRevenue]:
        return [r for r in self.platform_revenues if r.date == date]

    def save_daily_income(self, income: DailyIncome) -> None:
        self.daily_income[income.date] = income
        self._save()

    def get_daily_income(self, date: str) -> DailyIncome | None:
        return self.daily_income.get(date)

    def get_all_daily_income(self) -> list[DailyIncome]:
        return list(self.daily_income.values())

    def save_daily_expense(self, expense: DailyExpense) -> None:
        self.daily_expense[expense.date] = expense
        self._save()

    def get_daily_expense(self, date: str) -> DailyExpense | None:
        return self.daily_expense.get(date)

    def get_all_daily_expense(self) -> list[DailyExpense]:
        return list(self.daily_expense.values())

    def save_actual_consumption(self, consumption: ActualConsumption) -> None:
        self.actual_consumptions.append(consumption)
        self._save()

    def get_actual_consumptions(self, date: str) -> list[ActualConsumption]:
        return [c for c in self.actual_consumptions if c.date == date]

    def save_monthly_cost(self, cost: MonthlyFixedCost) -> None:
        self.monthly_costs[cost.month] = cost
        self._save()

    def get_monthly_cost(self, month: str) -> MonthlyFixedCost | None:
        return self.monthly_costs.get(month)


def _add_week(date_str: str) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=7)).strftime("%Y-%m-%d")
