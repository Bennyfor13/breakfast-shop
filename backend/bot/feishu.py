from __future__ import annotations
import json
import re
import time
from datetime import date, timedelta
import httpx
from fastapi import APIRouter, Request
from backend.bot.nlu import parse_intent, Intent
from backend.bot.llm_nlu import parse_intent_llm
from backend.bot.dispatcher import dispatch
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

# App base URL for webview deep-links
_base_url: str = "http://localhost:8000"

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


def set_base_url(url: str):
    global _base_url
    _base_url = url


def _add_app_link(card: dict, text: str, app_path: str) -> dict:
    """Append a webview jump button to a Feishu card."""
    import time
    card["card"]["elements"].append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": text},
            "type": "primary",
            "url": f"{_base_url}/app/{app_path}?t={int(time.time())}",
        }],
    })
    return card


def _add_nav_buttons(card: dict) -> dict:
    """Append quick-nav buttons for all main pages."""
    import time
    pages = [
        ("排班表", "schedule"),
        ("记账", "accounting"),
        ("备料采购", "inventory"),
        ("利润分析", "pricing"),
        ("员工管理", "staff"),
    ]
    actions = []
    for label, path in pages:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": label},
            "type": "default",
            "url": f"{_base_url}/app/{path}?t={int(time.time())}",
        })
    card["card"]["elements"].append({"tag": "action", "actions": actions})
    return card


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


def _day_name_cn(date_str: str) -> str:
    from datetime import datetime as dt
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    d = dt.strptime(date_str, "%Y-%m-%d")
    return names[d.weekday()]


def _parse_date_str(text: str, fallback: date | None = None) -> str:
    """Parse a date string from natural language. Supports:
    - Relative: 今天, 明天, 后天, 大后天
    - Day of week: 周一, 周二, ..., 周日 (next occurrence)
    - Absolute: 5月25日, 5.25, 5/25, 2026-05-25
    Returns YYYY-MM-DD format.
    """
    today = fallback or date.today()
    text = text.strip()

    # Relative days
    rel: dict[str, int] = {"今天": 0, "明天": 1, "后天": 2, "大后天": 3}
    for word, offset in rel.items():
        if word in text:
            return (today + timedelta(days=offset)).strftime("%Y-%m-%d")

    # Day of week (next occurrence, today counts)
    day_names = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6,
                 "星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4, "星期五": 5, "星期六": 6, "星期天": 6,
                 "礼拜一": 1, "礼拜二": 2, "礼拜三": 3, "礼拜四": 4, "礼拜五": 5, "礼拜六": 6, "礼拜天": 6}
    for word, target_dow in day_names.items():
        if word in text:
            days_ahead = target_dow - today.weekday()
            if days_ahead < 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Absolute dates with year
    import re
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # Absolute dates without year (assume current year)
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return f"{today.year:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{1,2})[./](\d{1,2})\b", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return f"{today.year:04d}-{mo:02d}-{d:02d}"

    return today.strftime("%Y-%m-%d")


def _resolve_date(raw_text: str, llm_date: str = "") -> str:
    """Resolve date from LLM param, falling back to text parsing.
    Validates LLM output — it may return raw day names like '周五'."""
    if llm_date and re.match(r"^\d{4}-\d{2}-\d{2}$", llm_date):
        return llm_date
    return _parse_date_str(raw_text)


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
    today = date.today()
    week_start = _get_week_start(today)
    shifts = store.get_shifts(week_start)

    shifts_by_date: dict[str, dict[str, list[str]]] = {}
    for s in shifts:
        shifts_by_date.setdefault(s.date, {}).setdefault(s.period, []).append(
            f"{_get_staff_name(s.staff_id)}"
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
    card = _build_card("排班", content)
    return _add_app_link(card, "打开排班表", "schedule")


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

    lines.append("---\n发送 **「确认工资」** 确认")
    content = "\n".join(lines)
    card = _build_card("工资单", content)
    return _add_app_link(card, "打开工资单", "payroll")


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


def _handle_mark_absent(params: dict, raw_text: str) -> dict:
    """Handle staff absence: parse date/week, auto-find replacements, reassign shifts."""
    from backend.modules.scheduling import auto_reschedule_day

    staff_name = params.get("staff_name", "")

    # If NLU gave a name that doesn't match, try known-name matching
    if staff_name and not _find_staff_by_name(staff_name):
        staff_name = ""
    if not staff_name:
        for s in (store.list_staff() if store else []):
            if s.name in raw_text:
                staff_name = s.name
                break

    if not staff_name:
        return _build_card("请假", "请提供员工姓名。例如：\n「张三周五休息」")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("请假", f"未找到员工「{staff_name}」，请确认姓名后再试。")

    # Check if this is a full-week absence
    is_full_week = bool(re.search(r"这[周星期]|本周|这个?星期|整周|一周", raw_text))

    if is_full_week:
        ws = date.today()
        monday = ws - timedelta(days=ws.weekday())
        all_replacements = []
        for i in range(7):
            d = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
            result = auto_reschedule_day(store, staff_id, d)
            if result["ok"]:
                all_replacements.extend(result["replacements"])

        if not all_replacements:
            return _build_card("排班调整", f"**{staff_name}** 本周无排班，无需调整。")

        by_date: dict[str, list] = {}
        for r in all_replacements:
            by_date.setdefault(r.get("date", ""), []).append(r)

        lines = [f"**{staff_name}** 本周休息，已自动安排替班：", ""]
        for d in sorted(by_date):
            day_label = f"{d} {_day_name_cn(d)}"
            periods = "、".join(f"{r['period']}→{r['replacement_name']}" for r in by_date[d])
            lines.append(f"- {day_label}: {periods}")

        lines.append("")
        lines.append(f"共调整 {len(all_replacements)} 个班次。")
        card = _build_card("排班调整", "\n".join(lines))
        return _add_app_link(card, "查看排班", "schedule")

    # Single-day absence
    date_str = _resolve_date(raw_text, params.get("date", ""))

    result = auto_reschedule_day(store, staff_id, date_str)
    if not result["ok"]:
        return _build_card("请假", result["reason"])

    replacements = result["replacements"]
    lines = [
        f"**{staff_name}** 在 **{date_str}** 休息，已自动安排替班：",
        "",
    ]
    for r in replacements:
        lines.append(f"- {r['period']}: {r['replacement_name']} 替班")

    lines.append("")
    lines.append(f"共 {len(replacements)} 个班次已重新分配。")
    content = "\n".join(lines)

    card = _build_card("排班调整", content)
    return _add_app_link(card, "查看排班", "schedule")


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
    import json as _json

    # Try JSON-encoded actions first
    try:
        data = _json.loads(value)
        if data.get("action") == "assign_replacement":
            from backend.modules.scheduling import assign_replacement
            result = assign_replacement(
                store, data["absent_id"], data["date"], data["replacement_id"],
            )
            if result["assigned"]:
                absent_name = _get_staff_name(data["absent_id"])
                repl_name = _get_staff_name(data["replacement_id"])
                card = _build_card("替班完成", f"已将 **{absent_name}** 在 {data['date']} 的 {result['shifts_replaced']} 个班次分配给 **{repl_name}**。")
                return _add_app_link(card, "查看排班", "schedule")
            return _build_card("替班失败", result.get("reason", "替班分配失败"))
    except (_json.JSONDecodeError, TypeError):
        pass

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
    date_str = _resolve_date("", params.get("date", "")) or date.today().strftime("%Y-%m-%d")
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
    date_str = params.get("date", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        date_str = date.today().strftime("%Y-%m-%d")

    if not staff_name:
        return _build_card("寻找替班", "请说明哪位员工需要替班。例如：\n「张三请假找谁替」")

    staff_id = _find_staff_by_name(staff_name)
    if not staff_id:
        return _build_card("寻找替班", f"未找到员工「{staff_name}」")

    existing = store.get_shifts_by_date(date_str)
    candidates = find_sub(store, staff_id, existing, date_str)

    if not candidates:
        return _build_card("寻找替班", f"{date_str} 暂无合适的替班人选替代 **{staff_name}**。")

    import json as _json
    names = "、".join(c.name for c in candidates[:5])
    card = _build_card(
        "寻找替班",
        f"**{staff_name}** 的替班人选（{date_str}）：\n{names}\n\n点击下方按钮确认，或发送「名字替{staff_name}」",
    )
    # Add a button for each of the top 3 candidates
    actions = []
    for c in candidates[:3]:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": f"选 {c.name} 替班"},
            "type": "primary",
            "value": _json.dumps({"action": "assign_replacement", "absent_id": staff_id, "replacement_id": c.id, "date": date_str}),
        })
    if actions:
        card["card"]["elements"].append({"tag": "action", "actions": actions})
    return card


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def handle_message(text: str) -> dict:
    # Fast path: "X替Y" pattern — directly assign replacement
    m = re.search(r"([\w一-鿿]{1,4})替([\w一-鿿]{1,4})", text)
    if m:
        repl_name, absent_name = m.group(1), m.group(2)
        absent_id = _find_staff_by_name(absent_name)
        repl_id = _find_staff_by_name(repl_name)
        if absent_id and repl_id:
            from backend.modules.scheduling import assign_replacement
            today_str = date.today().strftime("%Y-%m-%d")
            result = assign_replacement(store, absent_id, today_str, repl_id)
            if result["assigned"]:
                card = _build_card(
                    "替班完成",
                    f"已安排 **{repl_name}** 替 **{absent_name}** 的班（{today_str}，{result['shifts_replaced']} 个班次）。",
                )
                return _add_app_link(card, "查看排班", "schedule")
            return _build_card("替班失败", result.get("reason", "替班分配失败"))
        if not absent_id:
            return _build_card("替班", f"未找到员工「{absent_name}」")
        if not repl_id:
            return _build_card("替班", f"未找到员工「{repl_name}」")

    # Fast path: "功能" / "菜单" — show nav buttons
    if text.strip() in ("功能", "菜单", "帮助", "帮助", "?", "？"):
        card = _build_card("早餐助手", "点击下方按钮直接进入对应功能页面：")
        return _add_nav_buttons(card)

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
        return _handle_mark_absent(parsed.params, parsed.raw)

    if parsed.intent == Intent.MARK_OVERTIME:
        return _handle_mark_overtime(parsed.params, parsed.raw)

    if parsed.intent == Intent.CONFIRM_SCHEDULE:
        return _build_card("排班", "排班已确认发布。本周班表已生效。")

    if parsed.intent == Intent.EDIT_SCHEDULE:
        # If it looks like an absence/rest request, handle it directly
        if re.search(r"休息|请假|不来|缺勤|不上班|歇", text):
            return _handle_mark_absent(parsed.params, text)
        # If it looks like a single shift edit
        if re.search(r"换成|替换|换班|把.*换成", text):
            return _handle_edit_single_shift(parsed.params)
        # If it looks like finding a replacement
        if re.search(r"找谁替|谁替班|替班人选|找人替", text):
            return _handle_find_replacement(parsed.params)
        return _build_card(
            "排班调整",
            "请描述需要调整的内容，例如：\n"
            "- 「张三周五休息」\n"
            "- 「李四换成王五」\n"
            "- 「赵六明天请假」",
        )

    if parsed.intent == Intent.EDIT_SINGLE_SHIFT:
        return _handle_edit_single_shift(parsed.params)

    if parsed.intent == Intent.FIND_REPLACEMENT:
        return _handle_find_replacement(parsed.params)

    if parsed.intent == Intent.CONFIRM_PAYROLL:
        return _build_card("工资单", "工资单已确认。")

    # Help / unknown — check if it's just a staff name, then show fallback
    staff_id = _find_staff_by_name(text.strip())
    if staff_id:
        today = date.today()
        ws = _get_week_start(today)
        person_shifts = [s for s in store.get_shifts(ws) if s.staff_id == staff_id]
        if person_shifts:
            by_day: dict[str, list] = {}
            for s in person_shifts:
                by_day.setdefault(s.date, []).append(s.period)
            lines = [f"**{text.strip()}** 本周排班：", ""]
            for d in sorted(by_day):
                lines.append(f"- {d} {_day_name_cn(d)}: {'、'.join(by_day[d])}")
            return _build_card("员工排班", "\n".join(lines))
        return _build_card("员工排班", f"**{text.strip()}** 本周暂无排班。")

    card = _build_card("早餐助手", (
        "我可以帮你做这些：\n"
        "\n"
        "**排班**\n"
        "· 「查看排班」— 看本周排班\n"
        "· 「张三周五休息」— 自动找人替班\n"
        "· 「张三加班」— 记录加班\n"
        "\n"
        "**工资**\n"
        "· 「查看工资」— 看本月工资单\n"
        "\n"
        "**采购**\n"
        "· 「备料」— 查看采购清单\n"
        "· 「鲜肉包:100, 豆浆:50」— 输入销量出采购单\n"
        "\n"
        "**其他**\n"
        "· 「利润分析」— 看菜品毛利\n"
        "· 「新增员工…」— 添加员工\n"
        "· 「新增菜品…」— 添加菜品\n"
        "\n"
        "点击下方按钮直接打开对应页面："
    ))
    return _add_nav_buttons(card)


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

@feishu_router.get("/webhook")
async def feishu_webhook_get():
    return {"status": "ok", "message": "Feishu webhook endpoint ready"}


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
            sender_id = event.get("sender", {}).get("sender_id", {}).get("user_id", "default_user")
            card = await dispatch(store, text, sender_id, _llm_api_key, _llm_api_url)
            await _reply_message(message_id, card)

    return {"code": 0}
