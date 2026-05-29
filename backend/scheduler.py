"""APScheduler-based proactive push notifications for Feishu Bot."""
from __future__ import annotations
import json
import httpx
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.data.mock_store import MockStore

scheduler = AsyncIOScheduler()

# Store the boss's chat_id for proactive pushes
_boss_chat_id: str = ""
_store: MockStore | None = None
_feishu_token: str = ""

FEISHU_API = "https://open.feishu.cn/open-apis"


def init_scheduler(store: MockStore, feishu_token_provider):
    global _store
    _store = store
    scheduler.start()
    _schedule_jobs(feishu_token_provider)


def shutdown_scheduler():
    scheduler.shutdown(wait=False)


def set_boss_chat_id(chat_id: str):
    global _boss_chat_id
    _boss_chat_id = chat_id


async def send_proactive_message(card: dict, token: str):
    """Send a new message (not a reply) to the boss."""
    if not _boss_chat_id:
        return
    card_content = json.dumps(card["card"])
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FEISHU_API}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": _boss_chat_id,
                "content": card_content,
                "msg_type": "interactive",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data.get("code") != 0:
            print(f"Push send error: {data}")


def _build_push_card(title: str, content: str) -> dict:
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "markdown", "content": content}],
        },
    }


async def _push_morning_schedule(token_provider):
    """04:30 — Today's schedule push."""
    if not _store or not _boss_chat_id:
        return
    token = await token_provider()
    today = date.today().strftime("%Y-%m-%d")
    shifts = _store.get_shifts_by_date(today)

    if not shifts:
        content = f"## {today} 排班\n\n今日暂无排班，请及时安排。"
    else:
        by_period: dict[str, list[str]] = {}
        for s in shifts:
            by_period.setdefault(s.period, []).append(_get_staff_name(s.staff_id))
        lines = [f"## {today} 排班", ""]
        for period in ["早班", "晚班"]:
            names = by_period.get(period, ["—"])
            lines.append(f"**{period}**: {'、'.join(names)}")
        content = "\n".join(lines)

    card = _build_push_card("今日排班", content)
    from backend.bot.feishu import _add_app_link
    card = _add_app_link(card, "打开排班看板", "schedule")
    await send_proactive_message(card, token)


async def _push_evening_accounting(token_provider):
    """20:00 — Today's accounting summary."""
    if not _store or not _boss_chat_id:
        return
    token = await token_provider()
    today = date.today().strftime("%Y-%m-%d")

    income_record = _store.get_daily_income(today)
    expense_record = _store.get_daily_expense(today)

    income = income_record.income if income_record else {}
    expense = expense_record.expense if expense_record else {}
    total_income = sum(income.values())
    total_expense = sum(expense.values())
    net = total_income - total_expense

    lines = [f"## {today} 收支日报", ""]
    if total_income > 0 or total_expense > 0:
        if income:
            lines.append("**收入**")
            for k, v in sorted(income.items(), key=lambda x: -x[1]):
                lines.append(f"- {k}: ¥{v:.0f}")
            lines.append("")
        if expense:
            lines.append("**支出**")
            for k, v in sorted(expense.items(), key=lambda x: -x[1]):
                lines.append(f"- {k}: ¥{v:.0f}")
            lines.append("")
        lines.append(f"---\n**净利润: ¥{net:.0f}**")
    else:
        lines.append("今日暂无记账记录。")
        lines.append("")
        lines.append("如需记账请回复或点击下方按钮。")

    content = "\n".join(lines)
    card = _build_push_card("收支日报", content)
    from backend.bot.feishu import _add_app_link
    card = _add_app_link(card, "打开记账", "accounting")
    await send_proactive_message(card, token)


async def _push_monthly_payroll(token_provider):
    """Monthly 1st — Last month's payroll summary."""
    if not _store or not _boss_chat_id:
        return
    from backend.modules.payroll import generate_monthly_payroll

    token = await token_provider()
    today = date.today()
    first_of_month = today.replace(day=1)
    last_month = (first_of_month - timedelta(days=1)).strftime("%Y-%m")
    results = generate_monthly_payroll(_store, last_month)

    if not results:
        content = f"## {last_month} 工资单\n\n暂无数据。"
    else:
        total = sum(r["total"] for r in results)
        lines = [
            f"## {last_month} 工资汇总",
            "",
            "| 姓名 | 基础 | 奖金 | 合计 |",
            "|------|------|------|------|",
        ]
        for r in results:
            lines.append(
                f"| {r['staff_name']} | {r['base_pay']:.0f} | {r['performance_bonus']:.0f} | {r['total']:.0f} |"
            )
        lines.append("")
        lines.append(f"**合计: {total:.0f} 元**\n\n回复「确认工资」确认。")
        content = "\n".join(lines)

    card = _build_push_card("工资单", content)
    from backend.bot.feishu import _add_app_link
    card = _add_app_link(card, "查看工资明细", "payroll")
    await send_proactive_message(card, token)


def _get_staff_name(staff_id: str) -> str:
    if _store:
        s = _store.get_staff(staff_id)
        if s:
            return s.name
    return staff_id


def _schedule_jobs(token_provider):
    """Register all scheduled jobs."""
    # Morning schedule push at 04:30
    scheduler.add_job(
        _push_morning_schedule, "cron", hour=4, minute=30,
        args=[token_provider], id="morning_schedule",
        replace_existing=True,
    )
    # Evening accounting push at 20:00
    scheduler.add_job(
        _push_evening_accounting, "cron", hour=20, minute=0,
        args=[token_provider], id="evening_accounting",
        replace_existing=True,
    )
    # Monthly payroll on 1st at 09:07
    scheduler.add_job(
        _push_monthly_payroll, "cron", day=1, hour=9, minute=7,
        args=[token_provider], id="monthly_payroll",
        replace_existing=True,
    )
