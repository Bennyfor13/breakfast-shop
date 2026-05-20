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
    """06:00 — Today's schedule + prep reminders."""
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
            by_period.setdefault(s.period, []).append(s.staff_id)
        lines = [f"## {today} 排班", ""]
        for period in ["早班", "晚班"]:
            names = by_period.get(period, ["—"])
            lines.append(f"**{period}**: {', '.join(names)}")
        lines.append("")
        lines.append("请检查排班，如需调整请回复。")
        content = "\n".join(lines)

    card = _build_push_card("今日排班", content)
    await send_proactive_message(card, token)


async def _push_evening_reminder(token_provider):
    """20:00 — Attendance marking reminder."""
    if not _store or not _boss_chat_id:
        return
    token = await token_provider()
    today = date.today().strftime("%Y-%m-%d")
    existing = _store.get_attendance(today)

    absent_list = "、".join(existing.absent) if existing and existing.absent else "无"
    overtime_list = "、".join(existing.overtime) if existing and existing.overtime else "无"

    content = (
        f"## 考勤标记提醒 ({today})\n\n"
        f"今日缺勤: {absent_list}\n"
        f"今日加班: {overtime_list}\n\n"
        "如有变动请回复标记，例如：\n"
        "- 「张三请假」\n"
        "- 「李四加班」"
    )
    card = _build_push_card("考勤提醒", content)
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
    await send_proactive_message(card, token)


def _schedule_jobs(token_provider):
    """Register all scheduled jobs."""
    # Morning schedule push at 06:07
    scheduler.add_job(
        _push_morning_schedule, "cron", hour=6, minute=7,
        args=[token_provider], id="morning_schedule",
        replace_existing=True,
    )
    # Evening reminder at 20:07
    scheduler.add_job(
        _push_evening_reminder, "cron", hour=20, minute=7,
        args=[token_provider], id="evening_reminder",
        replace_existing=True,
    )
    # Monthly payroll on 1st at 09:07
    scheduler.add_job(
        _push_monthly_payroll, "cron", day=1, hour=9, minute=7,
        args=[token_provider], id="monthly_payroll",
        replace_existing=True,
    )
