from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import PlatformRevenue, DailyIncome, DailyExpense


def record_income(
    store: AbstractStore,
    date: str,
    income: dict[str, float]
) -> bool:
    """记录当日收入"""
    record = DailyIncome(date=date, income=income)
    store.save_daily_income(record)
    return True


def record_expense(
    store: AbstractStore,
    date: str,
    expense: dict[str, float]
) -> bool:
    """记录当日支出"""
    record = DailyExpense(date=date, expense=expense)
    store.save_daily_expense(record)
    return True


def get_daily_accounting(
    store: AbstractStore,
    date: str
) -> dict:
    """获取某日收支汇总"""
    income_record = store.get_daily_income(date)
    expense_record = store.get_daily_expense(date)

    income = income_record.income if income_record else {}
    expense = expense_record.expense if expense_record else {}

    total_income = sum(income.values())
    total_expense = sum(expense.values())

    return {
        "date": date,
        "income": income,
        "expense": expense,
        "total_income": total_income,
        "total_expense": total_expense
    }


def get_monthly_accounting(
    store: AbstractStore,
    year_month: str  # "2026-05"
) -> dict:
    """汇总某月所有收支"""
    income_by_platform: dict[str, float] = {}
    expense_by_platform: dict[str, float] = {}
    days_with_data = 0

    for record in store.get_all_daily_income():
        if record.date.startswith(year_month):
            days_with_data += 1
            for k, v in record.income.items():
                income_by_platform[k] = income_by_platform.get(k, 0) + v

    for record in store.get_all_daily_expense():
        if record.date.startswith(year_month):
            for k, v in record.expense.items():
                expense_by_platform[k] = expense_by_platform.get(k, 0) + v

    total_income = sum(income_by_platform.values())
    total_expense = sum(expense_by_platform.values())

    return {
        "year_month": year_month,
        "days_with_data": days_with_data,
        "income": income_by_platform,
        "expense": expense_by_platform,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense,
        "profit_rate": round((total_income - total_expense) / total_income * 100, 1) if total_income > 0 else 0,
    }


def record_platform_revenue(
    store: AbstractStore,
    date: str,
    revenues: dict[str, float]
) -> bool:
    """记录当日各平台收入"""
    for platform, amount in revenues.items():
        revenue = PlatformRevenue(
            date=date,
            platform=platform,
            amount=amount
        )
        store.save_platform_revenue(revenue)
    return True


def get_daily_revenue(
    store: AbstractStore,
    date: str
) -> dict:
    """获取某日总收入及平台明细"""
    revenues = store.get_platform_revenues(date)
    by_platform = {r.platform: r.amount for r in revenues}
    total = sum(by_platform.values())

    return {
        "date": date,
        "total": total,
        "by_platform": by_platform
    }
