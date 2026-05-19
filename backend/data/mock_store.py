from backend.data.interface import AbstractStore
from backend.data.models import (
    Staff, MenuItem, DemandTemplate, Shift, AttendanceLog,
    PerformanceScore, IngredientStock, SalesRecord, WasteFeedback,
)


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

    def list_staff(self) -> list[Staff]:
        return [s for s in self.staff.values() if s.active]

    def get_staff(self, staff_id: str) -> Staff | None:
        return self.staff.get(staff_id)

    def add_staff(self, staff: Staff) -> None:
        self.staff[staff.id] = staff

    def update_staff(self, staff: Staff) -> None:
        if staff.id in self.staff:
            self.staff[staff.id] = staff

    def delete_staff(self, staff_id: str) -> None:
        s = self.staff.get(staff_id)
        if s:
            s.active = False

    def list_menu(self) -> list[MenuItem]:
        return [m for m in self.menu.values() if m.active]

    def get_menu_item(self, item_id: str) -> MenuItem | None:
        return self.menu.get(item_id)

    def add_menu_item(self, item: MenuItem) -> None:
        self.menu[item.id] = item

    def update_menu_item(self, item: MenuItem) -> None:
        if item.id in self.menu:
            self.menu[item.id] = item

    def delete_menu_item(self, item_id: str) -> None:
        m = self.menu.get(item_id)
        if m:
            m.active = False

    def get_demand_template(self) -> DemandTemplate:
        return self.demand_template

    def set_demand_template(self, template: DemandTemplate) -> None:
        self.demand_template = template

    def save_shifts(self, shifts: list[Shift]) -> None:
        if not shifts:
            return
        week = shifts[0].date[:10]
        end = _add_week(week)
        self.shifts = [s for s in self.shifts if s.date < week or s.date >= end] + shifts

    def get_shifts(self, week_start: str) -> list[Shift]:
        end = _add_week(week_start)
        return [s for s in self.shifts if week_start <= s.date < end]

    def get_shifts_by_date(self, date: str) -> list[Shift]:
        return [s for s in self.shifts if s.date == date]

    def save_attendance(self, log: AttendanceLog) -> None:
        self.attendance[log.date] = log

    def get_attendance(self, date: str) -> AttendanceLog | None:
        return self.attendance.get(date)

    def list_attendance(self, from_date: str, to_date: str) -> list[AttendanceLog]:
        return [a for d, a in self.attendance.items() if from_date <= d <= to_date]

    def save_performance(self, score: PerformanceScore) -> None:
        self.performance.append(score)

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

    def add_sales(self, records: list[SalesRecord]) -> None:
        self.sales.extend(records)

    def get_sales(self, from_date: str, to_date: str) -> list[SalesRecord]:
        return [r for r in self.sales if from_date <= r.date <= to_date]

    def save_waste(self, feedback: WasteFeedback) -> None:
        self.waste = [w for w in self.waste if w.date != feedback.date]
        self.waste.append(feedback)

    def get_waste(self, from_date: str, to_date: str) -> list[WasteFeedback]:
        return [w for w in self.waste if from_date <= w.date <= to_date]


def _add_week(date_str: str) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=7)).strftime("%Y-%m-%d")
