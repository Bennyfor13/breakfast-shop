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

    # 3. Route to handler
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

    session.reset()
    return _build_card("提示", "参数不完整，请重新输入。")
