"""Unified dispatcher: session state machine + LLM NLU → business handlers."""
from __future__ import annotations
import re
from backend.bot.nlu import Intent, parse_intent as regex_parse
from backend.bot.llm_nlu import parse_intent_llm
from backend.bot.session import session_store, SessionState
from backend.data.mock_store import MockStore


async def dispatch(store: MockStore, text: str, user_id: str, llm_api_key: str = "", llm_api_url: str = "") -> dict:
    """Main entry point. Returns a dict suitable for _build_card()."""
    session = session_store.get(user_id)

    # 1. Handle active session state
    if session.state == SessionState.AWAITING_CONFIRMATION:
        return _handle_confirmation(session, text, store)

    if session.state == SessionState.COLLECTING_PARAMS:
        return await _handle_param_collection(session, text, store, llm_api_key, llm_api_url)

    # 2. Fresh input — run NLU
    parsed = await parse_intent_llm(text, llm_api_key, llm_api_url)

    # 3. Route to handler based on intent
    if parsed.intent == Intent.MULTI_DAY_ABSENCE:
        return await _handle_multi_day_absence(parsed, store, session)
    elif parsed.intent == Intent.WEEK_ABSENCE:
        return await _handle_week_absence(parsed, store, session)
    elif parsed.intent == Intent.RECORD_REVENUE:
        return await _handle_record_revenue(parsed, store)
    elif parsed.intent == Intent.QUERY_PROFIT:
        return await _handle_query_profit(parsed, store)
    elif parsed.intent == Intent.QUERY_CONSUMPTION:
        return await _handle_query_consumption(parsed, store, session)

    # 4. Default: pass to existing handler
    from backend.bot.feishu import handle_message
    return await handle_message(text)


def _handle_confirmation(session, text: str, store: MockStore) -> dict:
    from backend.bot.feishu import _build_card
    from backend.modules.scheduling import edit_shift as do_edit, assign_replacement

    yes_pattern = r"^(确认|是的|好|可以|行|OK|ok|对|是|嗯|1|Y|y|yes|Yes|YES)$"
    no_pattern = r"^(取消|不|否|算了|别|n|N|no|No|NO|0)$"

    if re.search(yes_pattern, text.strip()):
        action = session.pending_action
        params = session.pending_params
        session.reset()

        if action == "edit_shift":
            success = do_edit(store, params["date"], params["period"], params["old_staff_id"], params["new_staff_id"])
            if success:
                return _build_card("编辑班次", f"已将 {params['date']} {params['period']} 的排班替换为 {params.get('new_name', params['new_staff_id'])}")
            return _build_card("编辑班次", "替换失败，未找到对应排班记录。")

        if action == "assign_replacement":
            result = assign_replacement(store, params["absent_id"], params["date"], params.get("replacement_id"))
            if result["assigned"]:
                return _build_card("替班分配", f"已分配替班：{params['date']} 由 {result['replacement_id']} 替代")
            return _build_card("替班分配", f"分配失败：{result.get('reason', '未知错误')}")

        if action == "apply_multi_day_reschedule":
            from backend.modules.scheduling import edit_shift
            count = 0
            for s in params["suggestions"]:
                if edit_shift(store, s["date"], s["period"], s["original"], s["replacement_id"]):
                    count += 1
            return _build_card("排班完成", f"已完成 {count} 个班次的替换")

        if action == "apply_week_absence":
            from backend.modules.scheduling import edit_shift
            count = 0
            for r in params["replacements"]:
                if r["replacement_id"] and edit_shift(store, r["date"], r["period"], params["staff_id"], r["replacement_id"]):
                    count += 1
            return _build_card("排班完成", f"已完成 {count} 个班次的替换")

        return _build_card("提示", "操作已确认。")

    if re.search(no_pattern, text.strip()):
        session.reset()
        return _build_card("提示", "已取消。")

    # Ambiguous — remind what's pending
    return _build_card("确认", f"{session.confirm_message}\n\n请回复「确认」或「取消」")


async def _handle_param_collection(session, text: str, store: MockStore, llm_api_key: str, llm_api_url: str) -> dict:
    from backend.bot.feishu import _build_card

    # Try to extract missing params from text using LLM
    parsed = await parse_intent_llm(text, llm_api_key, llm_api_url)
    if parsed.params:
        session.pending_params.update(parsed.params)

    # Check if we have enough params now
    action = session.pending_action
    params = session.pending_params

    if action == "edit_shift":
        if "new_staff_name" in params or "new_staff_id" in params:
            session.state = SessionState.AWAITING_CONFIRMATION
            return _build_card("确认", f"确认将 {params.get('date','今天')} {params.get('period','早班')} 替换为 {params.get('new_staff_name','?')}？")

    if action == "await_actual_consumption":
        if text.strip() in ["一致", "一样", "对", "是"]:
            session.reset()
            return _build_card("原料消耗", "已记录，无差异")

        # Try to parse actual consumption from text
        if parsed.intent == Intent.RECORD_ACTUAL_CONSUMPTION:
            from backend.modules.daily_report import record_actual_consumption
            ingredients = parsed.params.get("ingredients", {})
            if ingredients:
                result = record_actual_consumption(store, params["date"], ingredients)
                session.reset()

                diff_text = "\n".join([
                    f"• {d['ingredient']}：理论{d['theoretical']:.0f}g，实际{d['actual']:.0f}g，{'多用' if d['difference']>0 else '少用'}{abs(d['difference']):.0f}g"
                    for d in result["differences"][:5]
                ])

                return _build_card("实际消耗已记录", f"差异如下：\n{diff_text}")

    session.reset()
    return _build_card("提示", "参数不完整，请重新输入。")


async def _handle_multi_day_absence(parsed, store, session):
    from backend.bot.feishu import _build_card
    from backend.modules.scheduling import auto_reschedule_multiple_days
    from datetime import datetime, timedelta

    staff_name = parsed.params.get("staff_name")
    dates = parsed.params.get("dates", [])

    if not staff_name or not dates:
        return _build_card("错误", "请提供员工姓名和日期")

    # Convert relative dates to absolute
    today = datetime.now()
    weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
    actual_dates = []
    for d in dates:
        if d in weekday_map:
            target_weekday = weekday_map[d]
            days_ahead = target_weekday - today.weekday()
            if days_ahead < 0:
                days_ahead += 7
            actual_dates.append((today + timedelta(days=days_ahead)).strftime("%Y-%m-%d"))

    # Find staff
    staff = next((s for s in store.list_staff() if s.name == staff_name), None)
    if not staff:
        return _build_card("错误", f"未找到员工：{staff_name}")

    result = auto_reschedule_multiple_days(store, staff.id, actual_dates)

    if not result["ok"]:
        return _build_card("排班", result.get("reason", "无法安排"))

    suggestions_text = "\n".join([
        f"• {s['date']} {s['period']} → 建议让{s['replacement_name']}替班"
        for s in result["suggestions"]
    ])

    session.pending_action = "apply_multi_day_reschedule"
    session.pending_params = {"staff_id": staff.id, "suggestions": result["suggestions"]}
    session.state = SessionState.AWAITING_CONFIRMATION
    session.confirm_message = f"{staff_name}在以下时间有排班：\n{suggestions_text}\n\n确认吗？"

    return _build_card("排班建议", session.confirm_message)


async def _handle_week_absence(parsed, store, session):
    from backend.bot.feishu import _build_card
    from backend.modules.scheduling import cancel_staff_for_week
    from datetime import datetime, timedelta

    staff_name = parsed.params.get("staff_name")
    period = parsed.params.get("period")

    if not staff_name:
        return _build_card("错误", "请提供员工姓名")

    staff = next((s for s in store.list_staff() if s.name == staff_name), None)
    if not staff:
        return _build_card("错误", f"未找到员工：{staff_name}")

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    week_start = monday.strftime("%Y-%m-%d")

    result = cancel_staff_for_week(store, staff.id, week_start, period)

    if not result["ok"]:
        return _build_card("排班", result.get("reason", "无法安排"))

    replacements_text = "\n".join([
        f"• {r['date']} {r['period']} → 建议让{r['replacement_name']}替"
        for r in result["replacements"][:10]
    ])

    session.pending_action = "apply_week_absence"
    session.pending_params = {"staff_id": staff.id, "replacements": result["replacements"]}
    session.state = SessionState.AWAITING_CONFIRMATION
    session.confirm_message = f"{staff_name}本周共{result['affected_shifts']}个班次：\n{replacements_text}\n\n确认吗？"

    return _build_card("排班建议", session.confirm_message)


async def _handle_record_revenue(parsed, store):
    from backend.bot.feishu import _build_card
    from backend.modules.accounting import record_platform_revenue
    from datetime import datetime

    revenues = parsed.params.get("revenues", {})
    if not revenues:
        return _build_card("错误", "请提供收入数据")

    date = datetime.now().strftime("%Y-%m-%d")
    record_platform_revenue(store, date, revenues)

    total = sum(revenues.values())
    detail = "\n".join([f"• {p}：{a}元" for p, a in revenues.items()])

    return _build_card("记账成功", f"已记录 {date} 收入：\n{detail}\n总计：{total}元")


async def _handle_query_profit(parsed, store):
    from backend.bot.feishu import _build_card
    from backend.modules.daily_report import calculate_daily_profit
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")
    report = calculate_daily_profit(store, date)

    breakdown = "\n".join([
        f"• {item['item']}：卖{item['sold']}份，赚{item['profit']}元"
        for item in report.item_breakdown[:5]
    ])

    message = f"""{date} 利润报告：
💰 总收入：{report.total_revenue}元
💸 总成本：{report.total_cost}元
✅ 净利润：{report.net_profit}元

单品明细：
{breakdown}"""

    return _build_card("利润报告", message)


async def _handle_query_consumption(parsed, store, session):
    from backend.bot.feishu import _build_card
    from backend.modules.daily_report import get_ingredient_consumption
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")
    consumption = get_ingredient_consumption(store, date)

    if not consumption:
        return _build_card("原料消耗", "今日暂无销售记录")

    consumption_text = "\n".join([
        f"• {name}：{amount/1000:.1f}kg" if amount >= 1000 else f"• {name}：{amount:.0f}g"
        for name, amount in list(consumption.items())[:10]
    ])

    session.pending_action = "await_actual_consumption"
    session.pending_params = {"date": date, "theoretical": consumption}
    session.state = SessionState.COLLECTING_PARAMS
    session.confirm_message = f"{date} 理论消耗：\n{consumption_text}\n\n实际消耗是否一致？\n回复「一致」或告诉我实际用量"

    return _build_card("原料消耗", session.confirm_message)
