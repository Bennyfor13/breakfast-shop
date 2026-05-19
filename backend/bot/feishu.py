from __future__ import annotations
from fastapi import APIRouter, Request
from backend.bot.nlu import parse_intent, Intent
from backend.data.mock_store import MockStore

feishu_router = APIRouter(prefix="/feishu")
store: MockStore | None = None


def set_store(s: MockStore):
    global store
    store = s


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


def handle_message(text: str) -> dict:
    parsed = parse_intent(text)

    if parsed.intent == Intent.SHOW_SCHEDULE:
        return _build_card("排班", "本周排班请查看网页看板 → [打开](http://127.0.0.1:8000)", [
            {"text": "确认发布", "value": "schedule_confirm"},
            {"text": "调整", "value": "schedule_edit"},
        ])

    if parsed.intent == Intent.SHOW_INVENTORY:
        return _build_card("备料清单", "今日备料需求已更新，查看详情 → [打开看板](http://127.0.0.1:8000)")

    if parsed.intent == Intent.SHOW_PAYROLL:
        return _build_card("工资单", "本月工资已计算完成 → [查看明细](http://127.0.0.1:8000)", [
            {"text": "确认", "value": "payroll_confirm"},
        ])

    if parsed.intent == Intent.ADD_STAFF:
        name = parsed.params.get("name", "?")
        return _build_card("新增员工", f"已记录：{name}\n请在网页后台补充完整信息。")

    return _build_card("早餐助手", f"收到。意图: {parsed.intent.name}\n参数: {parsed.params}")


@feishu_router.post("/webhook")
async def feishu_webhook(req: Request):
    body = await req.json()
    try:
        msg_content = body.get("event", {}).get("message", {}).get("content", "{}")
        import json
        text = json.loads(msg_content).get("text", "")
    except Exception:
        text = ""
    if not text:
        return {"msg_type": "text", "content": {"text": "未收到消息内容"}}
    return handle_message(text)
