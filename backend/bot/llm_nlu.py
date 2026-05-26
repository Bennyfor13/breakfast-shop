"""LLM-based NLU using DeepSeek API. Falls back to regex NLU on failure."""
from __future__ import annotations
import json
import httpx
from backend.bot.nlu import Intent, ParsedIntent, parse_intent as regex_parse

SYSTEM_PROMPT = """你是早餐店排班助手的意图识别模块。根据用户输入，返回JSON格式的意图和参数。

支持的意图:
- SHOW_SCHEDULE: 查询排班 (params: week_offset=0本周/1下周/-1上周)
- SHOW_PAYROLL: 查询工资 (params: year_month 如"2026-05")
- SHOW_INVENTORY: 查询备料/库存/采购
- SHOW_PRICING: 查询利润/定价分析
- ADD_STAFF: 添加员工 (params: name, roles列表, morning_rate, evening_rate)
- ADD_MENU: 添加菜品 (params: name, price)
- MARK_ABSENT: 标记缺勤 (params: staff_name, date 可选默认今天)
- MARK_OVERTIME: 标记加班 (params: staff_name, date 可选默认今天)
- CONFIRM_SCHEDULE: 确认/发布排班
- EDIT_SCHEDULE: 调整排班
- CONFIRM_PAYROLL: 确认工资单
- EDIT_SINGLE_SHIFT: 编辑单个班次 (params: staff_name, date, period 早班/晚班, new_staff_name 可选, action 替换/添加/删除)
- FIND_REPLACEMENT: 寻找替班人选 (params: staff_name, date 可选默认今天)
- MULTI_DAY_ABSENCE: 多天请假 (params: staff_name, dates 日期列表如["周三","周五"])
- WEEK_ABSENCE: 整周请假 (params: staff_name, period 可选"早班"/"晚班"/null表示全部)
- RECORD_REVENUE: 记录收入 (params: revenues 字典如{"美团":500,"饿了么":300})
- QUERY_PROFIT: 查询利润
- QUERY_CONSUMPTION: 查询原料消耗
- RECORD_ACTUAL_CONSUMPTION: 记录实际消耗 (params: ingredients 字典如{"面粉":6000,"猪肉":3000})

返回格式严格为JSON:
{"intent": "SHOW_SCHEDULE", "params": {}}

无法识别时返回:
{"intent": "UNKNOWN", "params": {}}

只返回JSON，不要任何其他文字。"""

INTENT_MAP: dict[str, Intent] = {
    "SHOW_SCHEDULE": Intent.SHOW_SCHEDULE,
    "SHOW_PAYROLL": Intent.SHOW_PAYROLL,
    "SHOW_INVENTORY": Intent.SHOW_INVENTORY,
    "SHOW_PRICING": Intent.SHOW_PRICING,
    "ADD_STAFF": Intent.ADD_STAFF,
    "ADD_MENU": Intent.ADD_MENU,
    "MARK_ABSENT": Intent.MARK_ABSENT,
    "MARK_OVERTIME": Intent.MARK_OVERTIME,
    "CONFIRM_SCHEDULE": Intent.CONFIRM_SCHEDULE,
    "EDIT_SCHEDULE": Intent.EDIT_SCHEDULE,
    "CONFIRM_PAYROLL": Intent.CONFIRM_PAYROLL,
    "EDIT_SINGLE_SHIFT": Intent.EDIT_SINGLE_SHIFT,
    "FIND_REPLACEMENT": Intent.FIND_REPLACEMENT,
    "MULTI_DAY_ABSENCE": Intent.MULTI_DAY_ABSENCE,
    "WEEK_ABSENCE": Intent.WEEK_ABSENCE,
    "RECORD_REVENUE": Intent.RECORD_REVENUE,
    "QUERY_PROFIT": Intent.QUERY_PROFIT,
    "QUERY_CONSUMPTION": Intent.QUERY_CONSUMPTION,
    "RECORD_ACTUAL_CONSUMPTION": Intent.RECORD_ACTUAL_CONSUMPTION,
    "UNKNOWN": Intent.UNKNOWN,
}


async def classify_intent(
    text: str, api_key: str, api_url: str = "https://api.deepseek.com/v1",
) -> ParsedIntent | None:
    """Call DeepSeek API for intent classification. Returns None on failure (caller should fall back)."""
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 256,
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            parsed = json.loads(content)
            intent_name = parsed.get("intent", "UNKNOWN")
            intent = INTENT_MAP.get(intent_name, Intent.UNKNOWN)
            return ParsedIntent(intent=intent, params=parsed.get("params", {}), raw=text)
    except Exception:
        return None


async def parse_intent_llm(
    text: str, api_key: str, api_url: str = "https://api.deepseek.com/v1",
) -> ParsedIntent:
    """Classify with LLM first, fall back to regex NLU."""
    llm_result = await classify_intent(text, api_key, api_url)
    if llm_result is not None:
        return llm_result
    return regex_parse(text)
