from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
import re


class Intent(Enum):
    SHOW_SCHEDULE = auto()
    SHOW_INVENTORY = auto()
    SHOW_PRICING = auto()
    SHOW_PAYROLL = auto()
    ADD_STAFF = auto()
    ADD_MENU = auto()
    MARK_ABSENT = auto()
    MARK_OVERTIME = auto()
    CONFIRM_SCHEDULE = auto()
    EDIT_SCHEDULE = auto()
    CONFIRM_PAYROLL = auto()
    EDIT_SINGLE_SHIFT = auto()
    FIND_REPLACEMENT = auto()
    UNKNOWN = auto()


@dataclass
class ParsedIntent:
    intent: Intent
    params: dict = field(default_factory=dict)
    raw: str = ""


INTENT_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.SHOW_SCHEDULE, ["排班", "班表", "下周.*班", "明天.*班", "今天.*班"]),
    (Intent.SHOW_INVENTORY, ["备料", "采购", "库存", "原料", "该买"]),
    (Intent.SHOW_PRICING, ["利润", "赚钱", "亏", "定价", "哪个.*品", "毛利率"]),
    (Intent.SHOW_PAYROLL, ["工资", "薪资", "发钱"]),
    (Intent.ADD_STAFF, ["新增员工", "添加员工", "加个员工"]),
    (Intent.ADD_MENU, ["新增菜品", "添加菜品", "加个菜"]),
    (Intent.MARK_ABSENT, ["请假", "不来", "缺勤"]),
    (Intent.MARK_OVERTIME, ["加班", "替班"]),
    (Intent.CONFIRM_SCHEDULE, ["确认排班", "发布排班", "排班确认"]),
    (Intent.EDIT_SCHEDULE, ["调整排班", "修改排班", "排班调整"]),
    (Intent.CONFIRM_PAYROLL, ["确认工资", "工资确认", "工资单确认"]),
    (Intent.EDIT_SINGLE_SHIFT, ["换成", "替换", "换班", "把.*换成"]),
    (Intent.FIND_REPLACEMENT, ["找谁替", "谁替班", "替班人选", "找人替"]),
]


def parse_intent(text: str) -> ParsedIntent:
    result = ParsedIntent(intent=Intent.UNKNOWN, raw=text)

    for intent, patterns in INTENT_PATTERNS:
        for pat in patterns:
            if re.search(pat, text):
                result.intent = intent
                break
        if result.intent != Intent.UNKNOWN:
            break

    # Extract params
    if result.intent == Intent.ADD_STAFF:
        name_match = re.search(r"(?:员工)([\w一-鿿]{1,4})", text)
        if name_match:
            result.params["name"] = name_match.group(1)
        role_match = re.findall(r"(后厨|传菜|收银)", text)
        if role_match:
            result.params["roles"] = role_match
        rate_match = re.search(r"早班(\d+).*晚班(\d+)", text)
        if rate_match:
            result.params["morning_rate"] = float(rate_match.group(1))
            result.params["evening_rate"] = float(rate_match.group(2))

    if result.intent == Intent.ADD_MENU:
        name_match = re.search(r"(?:菜品|菜)([\w一-鿿]{1,6})", text)
        if name_match:
            result.params["name"] = name_match.group(1)
        price_match = re.search(r"卖(\d+)", text)
        if price_match:
            result.params["price"] = float(price_match.group(1))

    if result.intent == Intent.MARK_ABSENT:
        name_match = re.search(r"([\w一-鿿]{1,4})(?:明天|今天|后天)?请假", text)
        if name_match:
            result.params["staff_name"] = name_match.group(1)

    return result
