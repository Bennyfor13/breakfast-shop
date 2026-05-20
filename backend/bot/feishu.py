from __future__ import annotations
import json
import re
import time
from datetime import date, timedelta
import httpx
from fastapi import APIRouter, Request
from backend.bot.nlu import parse_intent, Intent
from backend.bot.llm_nlu import parse_intent_llm
from backend.data.mock_store import MockStore
from backend.data.models import AttendanceLog, Role

feishu_router = APIRouter(prefix="/feishu")
store: MockStore | None = None

# Feishu API credentials
_app_id: str = ""
_app_secret: str = ""
_token_cache: dict[str, str | float] = {"token": "", "expires_at": 0}

# LLM config
_llm_api_key: str = ""
_llm_api_url: str = "https://api.deepseek.com/v1"

FEISHU_API = "https://open.feishu.cn/open-apis"


def set_store(s: MockStore):
    global store
    store = s


def set_feishu_credentials(app_id: str, app_secret: str):
    global _app_id, _app_secret
    _app_id = app_id
    _app_secret = app_secret


def set_llm_config(api_key: str, api_url: str = "https://api.deepseek.com/v1"):
    global _llm_api_key, _llm_api_url
    _llm_api_key = api_key
    _llm_api_url = api_url


def _build_card(title: str, content: str, actions: list[dict] | None = None) -> dict:
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [
                {"tag": "markdown", "content": content},
            ],
        },
    }
    if actions:
        card["card"]["elements"].append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": a["text"]}, "value": a["value"]}
                for a in actions
            ],
        })
    return card


def _get_week_start(d: date) -> str:
    """Monday of the week containing d."""
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def _find_staff_by_name(name: str) -> str | None:
    if store is None:
        return None
    for s in store.list_staff():
        if s.name == name:
            return s.id
    return None


def _get_staff_name(staff_id: str) -> str:
    if store is None:
        return staff_id
    staff = store.get_staff(staff_id)
    return staff.name if staff else staff_id


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def _handle_schedule() -> dict:
    from backend.modules.scheduling import generate_weekly_schedule

    today = date.today()
    week_start = _get_week_start(today)
    schedule = generate_weekly_schedule(store, week_start)

    shifts_by_date: dict[str, dict[str, list[str]]] = {}
    for s in schedule.shifts:
        shifts_by_date.setdefault(s.date, {}).setdefault(s.period, []).append(
            f"{_get_staff_name(s.staff_id)}({s.role.value})"
        )

    lines = [f"## 本周排班 ({schedule.week_start})", ""]
    for d in sorted(shifts_by_date.keys()):
        lines.append(f"**{d}**")
        for period in ["早班", "晚班"]:
            staff_list = shifts_by_date[d].get(period, ["—"])
            lines.append(f"- {period}: {', '.join(staff_list)}")
        lines.append("")

    lines.append("---\n发送 **「确认排班」** 发布 · 发送 **「调整排班」** 修改")
    content = "\n".join(lines)
    return _build_card("排班", content)


def _handle_inventory(params: dict, raw_text: str) -> dict:
    # Try to extract sales forecast from raw text (e.g. "m1:100,m2:50")
    sales_match = re.search(r"(\w+:\d+(?:,\s*\w+:\d+)*)", raw_text)
    if sales_match:
        predicted: dict[str, int] = {}
        for pair in sales_match.group(1).split(","):
            if ":" in pair:
                k, v = pair.split(":")
                predicted[k.strip()] = int(v.strip())
        if predicted:
            return _build_purchase_card(predicted)

    # Check if store has recent sales data
    today = date.today()
    recent_sales = store.get_sales(
        (today - timedelta(days=7)).strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
    )
    if recent_sales:
        predicted = _aggregate_sales(recent_sales)
        return _build_purchase_card(predicted)

    return _build_card(
        "备料清单",
        "请提供明日预计销量。格式示例：\n`鲜肉包:100, 豆浆:50`\n\n或通过网页看板录入后重试。",
    )


def _aggregate_sales(records) -> dict[str, int]:
    result: dict[str, int] = {}
    for r in records:
        result[r.item_id] = result.get(r.item_id, 0) + r.quantity
    return result


def _build_purchase_card(predicted: dict[str, int]) -> dict:
    from backend.modules.inventory import forecast_ingredient_needs, generate_purchase_list

    needs = forecast_ingredient_needs(store, predicted)
    purchases = generate_purchase_list(store, needs)

    if not purchases:
        return _build_card("备料清单", "当前库存充足，无需采购。")

    lines = ["## 采购清单", "", "| 原料 | 需采购 |", "|------|--------|"]
    for name, amount in sorted(purchases.items(), key=lambda x: -x[1]):
        stock = store.get_stock(name)
        unit = stock.unit if stock else "g"
        lines.append(f"| {name} | {amount}{unit} |")

    content = "\n".join(lines)
    return _build_card("备料清单", content)


def _handle_pricing() -> dict:
    from backend.modules.pricing import analyze_all_items

    today = date.today()
    sales_records = store.get_sales(
        (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
    )
    sales_volumes = _aggregate_sales(sales_records)

    results = analyze_all_items(store, 5000, 15000, 5000, sales_volumes)

    if not results:
        return _build_card("利润分析", "暂无菜单数据。")

    top5 = results[:5]
    lines = ["## 利润分析 Top 5", "", "| 菜品 | 售价 | 成本 | 毛利 | 分类 |", "|------|------|------|------|------|"]
    for r in top5:
        lines.append(
            f"| {r['item_name']} | {r['selling_price']} | {r['total_cost']} | "
            f"{r['gross_profit']} ({r['margin_pct']}%) | {r['quadrant']} |"
        )

    content = "\n".join(lines)
    return _build_card("利润分析", content)


def _handle_payroll() -> dict:
    from backend.modules.payroll import generate_monthly_payroll

    today = date.today()
    year_month = today.strftime("%Y-%m")
    results = generate_monthly_payroll(store, year_month)

    if not results:
        return _build_card("工资单", "本月暂无排班数据，请先生成排班后再查询。")

    total = sum(r["total"] for r in results)
    lines = [
        "## 本月工资",
        "",
        "| 姓名 | 早班 | 晚班 | 绩效 | 合计 |",
        "|------|------|------|------|------|",
    ]
    for r in results:
        lines.append(
            f"| {r['staff_name']} | {r['morning_shifts']} | {r['evening_shifts']} | "
            f"{r['performance_bonus']:.0f} | {r['total']:.0f} |"
        )
    lines.append("")
    lines.append(f"**合计: {total:.0f} 元**")

    content = "\n".join(lines)
    lines.append("---\n发送 **「确认工资」** 确认")
    content = "\n".join(lines)
    return _build_card("工资单", content)


def _handle_add_staff(params: dict) -> dict:
    from backend.modules.base_data import create_staff

    name = params.get("name")
    if not name:
        return _build_card("新增员工", "请提供员工信息。格式示例：\n`新增员工老王，后厨，早班80晚班60`")

    roles_str = params.get("roles", [])
    roles = [Role(r) for r in roles_str] if roles_str else [Role.KITCHEN]
    morning_rate = params.get("morning_rate", 80.0)
    evening_rate = params.get("evening_rate", 60.0)

    staff = create_staff(store, None, name, roles, morning_rate, evening_rate)

    roles_display = ", ".join(r.value for r in staff.roles)
    content = (
        f"已添加员工：**{name}**\n"
        f"- 角色：{roles_display}\n"
        f"- 早班：{morning_rate} 元/班\n"
        f"- 晚班：{evening_rate} 元/班"
    )
    return _build_card("新增员工", content)


def _handle_mark_absent(params: dict) -> dict:
    staff_name = params.get("staff_name")
    if not staff_name:
        return _build_card("请假", "请提供员工姓名。格式示例：\n`张三请假`")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("请假", f"未找到员工「{staff_name}」，请确认姓名后再试。")

    today_str = date.today().strftime("%Y-%m-%d")
    existing = store.get_attendance(today_str)

    if existing:
        if staff_id not in existing.absent:
            existing.absent.append(staff_id)
        store.save_attendance(existing)
    else:
        store.save_attendance(AttendanceLog(date=today_str, absent=[staff_id]))

    return _build_card("请假", f"已记录：**{staff_name}** 今日（{today_str}）缺勤。")


def _handle_mark_overtime(params: dict, raw_text: str) -> dict:
    staff_name = params.get("staff_name")
    # NLU doesn't extract name for overtime — try from raw text
    if not staff_name:
        m = re.search(r"([\w一-鿿]{1,4})(?:今天|明天|后天)?(?:加班|替班)", raw_text)
        if m:
            staff_name = m.group(1)

    if not staff_name:
        return _build_card("加班", "请提供员工姓名。格式示例：\n`张三加班`")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("加班", f"未找到员工「{staff_name}」，请确认姓名后再试。")

    today_str = date.today().strftime("%Y-%m-%d")
    existing = store.get_attendance(today_str)

    if existing:
        if staff_id not in existing.overtime:
            existing.overtime.append(staff_id)
        store.save_attendance(existing)
    else:
        store.save_attendance(AttendanceLog(date=today_str, overtime=[staff_id]))

    return _build_card("加班", f"已记录：**{staff_name}** 今日（{today_str}）加班。")


# ---------------------------------------------------------------------------
# Card action handler
# ---------------------------------------------------------------------------

def _handle_card_action(value: str) -> dict:
    if value == "schedule_confirm":
        return _build_card("排班", "排班已确认发布。")

    if value == "schedule_edit":
        return _build_card(
            "排班调整",
            "请描述需要调整的内容，例如：\n"
            "- 「张三周一换成晚班」\n"
            "- 「周五早班加一个后厨」\n"
            "- 「李四周三请假，找替班」",
        )

    if value == "payroll_confirm":
        return _build_card("工资单", "工资单已确认。")

    return _build_card("提示", f"未知操作: {value}")


def _handle_add_menu(params: dict) -> dict:
    from backend.modules.base_data import create_menu_item

    name = params.get("name")
    if not name:
        return _build_card("新增菜品", "请提供菜品信息。格式示例：\n`新增菜品鲜肉包，卖3块`")
    price = params.get("price", 0.0)
    item = create_menu_item(store, None, name, price)
    return _build_card("新增菜品", f"已添加菜品：**{name}**\n售价：{price} 元")


def _handle_edit_single_shift(params: dict) -> dict:
    from backend.modules.scheduling import edit_shift as do_edit

    staff_name = params.get("staff_name", "")
    date_str = params.get("date", date.today().strftime("%Y-%m-%d"))
    period = params.get("period", "早班")
    new_name = params.get("new_staff_name", "")

    if not staff_name:
        return _build_card("编辑班次", "请说明要调整哪个员工的班次。例如：\n「把张三周三早班换成李四」")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("编辑班次", f"未找到员工「{staff_name}」")

    if new_name:
        new_id = _find_staff_by_name(new_name)
        if not new_id:
            return _build_card("编辑班次", f"未找到替班员工「{new_name}」")
        success = do_edit(store, date_str, period, staff_id, new_id)
        if success:
            return _build_card("编辑班次", f"已将 {date_str} {period} 的 **{staff_name}** 替换为 **{new_name}**")
        return _build_card("编辑班次", f"{date_str} {period} 未找到 **{staff_name}** 的排班记录")

    return _build_card("编辑班次", f"**{staff_name}** 在 {date_str} {period} 有排班。请输入替班员工姓名。\n例如：「换成李四」")


def _handle_find_replacement(params: dict) -> dict:
    from backend.modules.scheduling import find_replacement as find_sub

    staff_name = params.get("staff_name", "")
    date_str = params.get("date", date.today().strftime("%Y-%m-%d"))

    if not staff_name:
        return _build_card("寻找替班", "请说明哪位员工需要替班。例如：\n「张三请假找谁替」")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("寻找替班", f"未找到员工「{staff_name}」")

    existing = store.get_shifts_by_date(date_str)
    candidates = find_sub(store, staff_id, existing, date_str)

    if not candidates:
        return _build_card("寻找替班", f"{date_str} 暂无合适的替班人选替代 **{staff_name}**。")

    names = ", ".join(c.name for c in candidates[:5])
    return _build_card("寻找替班", f"**{staff_name}** 的替班人选（{date_str}）：\n{names}\n\n发送「{candidates[0].name}替{staff_name}」确认分配")


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def handle_message(text: str) -> dict:
    parsed = await parse_intent_llm(text, _llm_api_key, _llm_api_url)

    if parsed.intent == Intent.SHOW_SCHEDULE:
        return _handle_schedule()

    if parsed.intent == Intent.SHOW_INVENTORY:
        return _handle_inventory(parsed.params, parsed.raw)

    if parsed.intent == Intent.SHOW_PRICING:
        return _handle_pricing()

    if parsed.intent == Intent.SHOW_PAYROLL:
        return _handle_payroll()

    if parsed.intent == Intent.ADD_STAFF:
        return _handle_add_staff(parsed.params)

    if parsed.intent == Intent.ADD_MENU:
        return _handle_add_menu(parsed.params)

    if parsed.intent == Intent.MARK_ABSENT:
        return _handle_mark_absent(parsed.params)

    if parsed.intent == Intent.MARK_OVERTIME:
        return _handle_mark_overtime(parsed.params, parsed.raw)

    if parsed.intent == Intent.CONFIRM_SCHEDULE:
        return _build_card("排班", "排班已确认发布。本周班表已生效。")

    if parsed.intent == Intent.EDIT_SCHEDULE:
        return _build_card(
            "排班调整",
            "请描述需要调整的内容，例如：\n"
            "- 「张三周一换成晚班」\n"
            "- 「周五早班加一个后厨」\n"
            "- 「李四周三请假，找替班」",
        )

    if parsed.intent == Intent.EDIT_SINGLE_SHIFT:
        return _handle_edit_single_shift(parsed.params)

    if parsed.intent == Intent.FIND_REPLACEMENT:
        return _handle_find_replacement(parsed.params)

    if parsed.intent == Intent.CONFIRM_PAYROLL:
        return _build_card("工资单", "工资单已确认。")

    return _build_card("早餐助手", f"收到。意图: {parsed.intent.name}\n参数: {parsed.params}")


# ---------------------------------------------------------------------------
# Feishu API helpers
# ---------------------------------------------------------------------------

async def _get_tenant_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < float(_token_cache["expires_at"]) - 60:
        return str(_token_cache["token"])

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
            json={"app_id": _app_id, "app_secret": _app_secret},
        )
        data = resp.json()
        if data.get("code") == 0:
            _token_cache["token"] = data["tenant_access_token"]
            _token_cache["expires_at"] = now + data.get("expire", 7200)
            return str(_token_cache["token"])
        raise RuntimeError(f"Failed to get tenant access token: {data}")


async def _reply_message(message_id: str, card: dict):
    token = await _get_tenant_access_token()
    card_content = json.dumps(card["card"])
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FEISHU_API}/im/v1/messages/{message_id}/reply",
            json={"content": card_content, "msg_type": "interactive"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data.get("code") != 0:
            print(f"Feishu reply error: {data}")


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@feishu_router.post("/webhook")
async def feishu_webhook(req: Request):
    body = await req.json()

    # Feishu URL verification
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}

    header = body.get("header", {})
    event_type = header.get("event_type", "")
    event = body.get("event", {})

    # Card action (button clicks)
    if event_type == "card.action.trigger":
        action_value = event.get("action", {}).get("value", "")
        open_message_id = event.get("open_message_id", "")
        if action_value and open_message_id:
            card = _handle_card_action(action_value)
            await _reply_message(open_message_id, card)
        return {"code": 0}

    # Text message
    if event_type == "im.message.receive_v1":
        message = event.get("message", {})
        message_id = message.get("message_id", "")
        chat_id = message.get("chat_id", "")
        if chat_id:
            from backend.scheduler import set_boss_chat_id
            set_boss_chat_id(chat_id)
        try:
            text = json.loads(message.get("content", "{}")).get("text", "")
        except (json.JSONDecodeError, AttributeError):
            text = ""

        if text and message_id:
            card = await handle_message(text)
            await _reply_message(message_id, card)

    return {"code": 0}
