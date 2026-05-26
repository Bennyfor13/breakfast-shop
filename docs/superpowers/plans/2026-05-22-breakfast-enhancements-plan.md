# 早餐店助手功能增强 - 实施计划

**基于设计文档：** `docs/superpowers/specs/2026-05-22-breakfast-enhancements-design.md`  
**预计总时长：** 10小时  
**实施顺序：** 数据模型 → 排班增强 → 记账模块 → 利润追踪 → Bot集成

---

## Phase 1: 数据模型 (预计1小时)

### Task 1.1: 添加新数据模型到 models.py (15分钟)

**文件：** `backend/data/models.py`

**操作：** 在文件末尾添加4个新模型

```python
class PlatformRevenue(BaseModel):
    """老板每日按平台录入的收入"""
    date: str  # "2026-05-22"
    platform: str  # "美团" | "饿了么" | "堂食" | "其他"
    amount: float
    note: str = ""


class DailyProfitReport(BaseModel):
    """每日利润汇总"""
    date: str
    total_revenue: float
    total_cost: float
    net_profit: float
    item_breakdown: list[dict]
    ingredient_consumption: dict[str, float]


class ActualConsumption(BaseModel):
    """实际原料消耗 vs 理论消耗"""
    date: str
    ingredient_name: str
    theoretical: float
    actual: float
    difference: float
    note: str = ""


class MonthlyFixedCost(BaseModel):
    """月度固定成本配置"""
    month: str  # "2026-05"
    rent: float
    utilities: float
    other: float
    
    def daily_cost(self, days_in_month: int = 30) -> float:
        return (self.rent + self.utilities + self.other) / days_in_month
```

**验证：** 运行 `python -c "from backend.data.models import PlatformRevenue, MonthlyFixedCost"`

---

### Task 1.2: 扩展 AbstractStore 接口 (20分钟)

**文件：** `backend/data/interface.py`

**操作：** 在 `AbstractStore` 类中添加新方法

```python
# 平台收入相关
def save_platform_revenue(self, revenue: PlatformRevenue) -> None:
    raise NotImplementedError

def get_platform_revenues(self, date: str) -> list[PlatformRevenue]:
    raise NotImplementedError

# 实际消耗相关
def save_actual_consumption(self, consumption: ActualConsumption) -> None:
    raise NotImplementedError

def get_actual_consumptions(self, date: str) -> list[ActualConsumption]:
    raise NotImplementedError

# 固定成本相关
def save_monthly_cost(self, cost: MonthlyFixedCost) -> None:
    raise NotImplementedError

def get_monthly_cost(self, month: str) -> MonthlyFixedCost | None:
    raise NotImplementedError
```

---

### Task 1.3: 实现 MockStore 存储逻辑 (25分钟)

**文件：** `backend/data/mock_store.py`

**操作：** 在 `MockStore` 类中实现新方法

```python
def __init__(self):
    # ... 现有初始化 ...
    self._platform_revenues: list[PlatformRevenue] = []
    self._actual_consumptions: list[ActualConsumption] = []
    self._monthly_costs: dict[str, MonthlyFixedCost] = {}

def save_platform_revenue(self, revenue: PlatformRevenue) -> None:
    self._platform_revenues.append(revenue)

def get_platform_revenues(self, date: str) -> list[PlatformRevenue]:
    return [r for r in self._platform_revenues if r.date == date]

def save_actual_consumption(self, consumption: ActualConsumption) -> None:
    self._actual_consumptions.append(consumption)

def get_actual_consumptions(self, date: str) -> list[ActualConsumption]:
    return [c for c in self._actual_consumptions if c.date == date]

def save_monthly_cost(self, cost: MonthlyFixedCost) -> None:
    self._monthly_costs[cost.month] = cost

def get_monthly_cost(self, month: str) -> MonthlyFixedCost | None:
    return self._monthly_costs.get(month)
```

**验证：** 运行现有测试确保没有破坏

---

## Phase 2: 排班增强 (预计2小时)

### Task 2.1: 实现多天请假处理函数 (45分钟)

**文件：** `backend/modules/scheduling.py`

**操作：** 在文件末尾添加新函数

```python
def auto_reschedule_multiple_days(
    store: AbstractStore, 
    staff_id: str, 
    dates: list[str]
) -> dict:
    """处理某人多天请假，自动找替班人"""
    from datetime import datetime, timedelta
    
    all_suggestions = []
    
    for date_str in dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        monday = dt - timedelta(days=dt.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        
        # 确保该周排班存在
        all_week = store.get_shifts(week_start)
        if not all_week:
            schedule = generate_weekly_schedule(store, week_start)
            store.save_shifts(schedule.shifts)
            all_week = schedule.shifts
        
        # 找出该员工在这一天的所有班次
        existing = store.get_shifts_by_date(date_str)
        absent_shifts = [s for s in existing if s.staff_id == staff_id]
        
        if not absent_shifts:
            continue
        
        # 计算本周班次统计
        shift_counts = {}
        for s in all_week:
            shift_counts[s.staff_id] = shift_counts.get(s.staff_id, 0) + 1
        
        # 为每个班次找替班人
        for shift in absent_shifts:
            busy_ids = {s.staff_id for s in existing if s.period == shift.period}
            busy_ids.add(staff_id)
            
            candidates = find_replacement(store, staff_id, existing, date_str)
            candidates = [c for c in candidates if c.id not in busy_ids]
            candidates = sorted(candidates, key=lambda c: shift_counts.get(c.id, 0))
            
            if candidates:
                replacement = candidates[0]
                all_suggestions.append({
                    "date": date_str,
                    "period": shift.period,
                    "original": staff_id,
                    "replacement_id": replacement.id,
                    "replacement_name": replacement.name
                })
    
    return {
        "ok": True if all_suggestions else False,
        "suggestions": all_suggestions,
        "reason": "该员工在指定日期无排班" if not all_suggestions else None
    }
```

**验证：** 编写单元测试 `tests/test_scheduling_multi_day.py`

---

### Task 2.2: 实现整周取消函数 (45分钟)

**文件：** `backend/modules/scheduling.py`

**操作：** 继续添加

```python
def cancel_staff_for_week(
    store: AbstractStore,
    staff_id: str,
    week_start: str,
    period_filter: str | None = None
) -> dict:
    """取消某人整周（或整周某时段）的班次，自动找替班"""
    all_week = store.get_shifts(week_start)
    if not all_week:
        schedule = generate_weekly_schedule(store, week_start)
        store.save_shifts(schedule.shifts)
        all_week = schedule.shifts
    
    # 找出要取消的班次
    target_shifts = [
        s for s in all_week 
        if s.staff_id == staff_id and (period_filter is None or s.period == period_filter)
    ]
    
    if not target_shifts:
        return {
            "ok": False,
            "reason": f"该员工本周{'所有' if not period_filter else period_filter}班次为空"
        }
    
    # 计算班次统计
    shift_counts = {}
    for s in all_week:
        shift_counts[s.staff_id] = shift_counts.get(s.staff_id, 0) + 1
    
    replacements = []
    active = store.list_staff()
    
    for shift in target_shifts:
        existing_on_date = [s for s in all_week if s.date == shift.date]
        busy_ids = {s.staff_id for s in existing_on_date if s.period == shift.period}
        busy_ids.add(staff_id)
        
        candidates = sorted(
            [s for s in active if s.id not in busy_ids],
            key=lambda s: shift_counts.get(s.id, 0)
        )
        
        if candidates:
            replacement = candidates[0]
            replacements.append({
                "date": shift.date,
                "period": shift.period,
                "original": staff_id,
                "replacement_id": replacement.id,
                "replacement_name": replacement.name
            })
            shift_counts[replacement.id] = shift_counts.get(replacement.id, 0) + 1
        else:
            replacements.append({
                "date": shift.date,
                "period": shift.period,
                "original": staff_id,
                "replacement_id": None,
                "replacement_name": "无合适人选"
            })
    
    return {
        "ok": True,
        "affected_shifts": len(target_shifts),
        "replacements": replacements
    }
```

**验证：** 编写单元测试

---

## Phase 3: 记账模块 (预计1小时)

### Task 3.1: 创建 accounting.py 模块 (30分钟)

**文件：** `backend/modules/accounting.py` (新建)

```python
from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import PlatformRevenue


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
```

**验证：** 运行 `pytest tests/test_accounting.py`

---

## Phase 4: 利润追踪模块 (预计2小时)

### Task 4.1: 创建 daily_report.py 基础结构 (40分钟)

**文件：** `backend/modules/daily_report.py` (新建)

```python
from __future__ import annotations
from backend.data.interface import AbstractStore
from backend.data.models import DailyProfitReport, ActualConsumption
from backend.modules.accounting import get_daily_revenue
from backend.modules.pricing import calculate_item_cost


def get_ingredient_consumption(
    store: AbstractStore,
    date: str
) -> dict[str, float]:
    """计算某日理论原料消耗"""
    sales = store.get_sales_by_date(date)
    consumption = {}
    
    for sale in sales:
        item = store.get_menu_item(sale.item_id)
        if not item:
            continue
        for ing in item.bom:
            consumption[ing.name] = consumption.get(ing.name, 0) + ing.amount * sale.quantity
    
    return consumption


def record_actual_consumption(
    store: AbstractStore,
    date: str,
    actual: dict[str, float]
) -> dict:
    """记录实际原料消耗，并计算与理论值的差异"""
    theoretical = get_ingredient_consumption(store, date)
    differences = []
    
    for name, actual_val in actual.items():
        theo_val = theoretical.get(name, 0)
        diff = actual_val - theo_val
        pct = (diff / theo_val * 100) if theo_val > 0 else 0
        
        consumption = ActualConsumption(
            date=date,
            ingredient_name=name,
            theoretical=theo_val,
            actual=actual_val,
            difference=diff
        )
        store.save_actual_consumption(consumption)
        
        differences.append({
            "ingredient": name,
            "theoretical": theo_val,
            "actual": actual_val,
            "difference": diff,
            "percentage": round(pct, 1)
        })
    
    return {"date": date, "differences": differences}
```

**验证：** 基础功能测试

---

### Task 4.2: 实现利润计算函数 (50分钟)

**文件：** `backend/modules/daily_report.py`

**操作：** 继续添加

```python
def calculate_daily_profit(
    store: AbstractStore,
    date: str
) -> DailyProfitReport:
    """计算某日利润"""
    from datetime import datetime
    
    # 获取总收入
    revenue_data = get_daily_revenue(store, date)
    total_revenue = revenue_data["total"]
    
    # 获取销售记录
    sales = store.get_sales_by_date(date)
    
    # 计算原料成本
    raw_cost = 0
    item_breakdown = []
    
    for sale in sales:
        item = store.get_menu_item(sale.item_id)
        if not item:
            continue
        
        # 计算单品原料成本
        item_raw_cost = sum(
            ing.amount * 0.01  # 简化：使用默认单价
            for ing in item.bom
        ) * sale.quantity
        
        raw_cost += item_raw_cost
        
        item_revenue = sale.revenue
        item_profit = item_revenue - item_raw_cost
        
        item_breakdown.append({
            "item": item.name,
            "sold": sale.quantity,
            "revenue": item_revenue,
            "cost": item_raw_cost,
            "profit": item_profit
        })
    
    # 计算人工成本（简化：从排班获取）
    dt = datetime.strptime(date, "%Y-%m-%d")
    shifts = store.get_shifts_by_date(date)
    labor_cost = len(shifts) * 80  # 简化：每班80元
    
    # 计算固定成本
    month = date[:7]  # "2026-05"
    monthly_cost = store.get_monthly_cost(month)
    fixed_cost = monthly_cost.daily_cost() if monthly_cost else 100
    
    total_cost = raw_cost + labor_cost + fixed_cost
    net_profit = total_revenue - total_cost
    
    return DailyProfitReport(
        date=date,
        total_revenue=total_revenue,
        total_cost=total_cost,
        net_profit=net_profit,
        item_breakdown=item_breakdown,
        ingredient_consumption=get_ingredient_consumption(store, date)
    )
```

**验证：** 运行 `pytest tests/test_daily_report.py`

---

## Phase 5: Bot集成 (预计4小时)

### Task 5.1: 扩展NLU解析 (1小时)

**文件：** `backend/bot/llm_nlu.py`

**操作：** 添加新意图解析

```python
# 在现有 parse_intent_llm 函数中添加新意图识别
# 新增意图类型：
# - multi_day_absence: 多天请假
# - week_absence: 整周请假
# - record_revenue: 记录收入
# - query_profit: 查询利润
# - query_consumption: 查询原料消耗
# - record_actual_consumption: 记录实际消耗

# 示例提示词扩展：
"""
识别以下意图并提取参数：
- 多天请假: "小王周三周五没空" → {intent: "multi_day_absence", staff_name: "小王", dates: ["周三", "周五"]}
- 整周请假: "小李这周都不来了" → {intent: "week_absence", staff_name: "小李", scope: "整周"}
- 记录收入: "今天美团500饿了么300" → {intent: "record_revenue", revenues: {"美团": 500, "饿了么": 300}}
- 查询利润: "今天赚了多少" → {intent: "query_profit"}
- 查询消耗: "今天用了多少原料" → {intent: "query_consumption"}
- 记录实际消耗: "面粉6kg猪肉3kg" → {intent: "record_actual_consumption", ingredients: {"面粉": 6000, "猪肉": 3000}}
"""
```

**验证：** 测试各种输入格式

---

### Task 5.2: 更新dispatcher处理逻辑 (1.5小时)

**文件：** `backend/bot/dispatcher.py`

**操作：** 添加新场景处理

```python
async def dispatch(store: MockStore, text: str, user_id: str, llm_api_key: str = "", llm_api_url: str = "") -> dict:
    session = session_store.get(user_id)
    
    # 处理会话状态
    if session.state == SessionState.AWAITING_CONFIRMATION:
        return _handle_confirmation(session, text, store)
    
    if session.state == SessionState.COLLECTING_PARAMS:
        return await _handle_param_collection(session, text, store, llm_api_key, llm_api_url)
    
    # 新增：处理实际消耗录入状态
    if session.state == SessionState.AWAITING_ACTUAL_CONSUMPTION:
        return await _handle_actual_consumption(session, text, store, llm_api_key, llm_api_url)
    
    # NLU解析
    parsed = await parse_intent_llm(text, llm_api_key, llm_api_url)
    
    # 路由到对应处理器
    if parsed.intent == "multi_day_absence":
        return await _handle_multi_day_absence(parsed, store, session)
    elif parsed.intent == "week_absence":
        return await _handle_week_absence(parsed, store, session)
    elif parsed.intent == "record_revenue":
        return await _handle_record_revenue(parsed, store)
    elif parsed.intent == "query_profit":
        return await _handle_query_profit(parsed, store)
    elif parsed.intent == "query_consumption":
        return await _handle_query_consumption(parsed, store, session)
    
    # 默认处理
    from backend.bot.feishu import handle_message
    return await handle_message(text)
```

**验证：** 集成测试每个场景

---

### Task 5.3: 实现各场景处理函数 (1.5小时)

**文件：** `backend/bot/dispatcher.py`

**操作：** 添加处理函数

```python
async def _handle_multi_day_absence(parsed, store, session):
    from backend.modules.scheduling import auto_reschedule_multiple_days
    from backend.bot.feishu import _build_card
    
    staff_name = parsed.params.get("staff_name")
    dates = parsed.params.get("dates")  # 需要转换为实际日期
    
    # 转换相对日期为绝对日期
    actual_dates = _convert_relative_dates(dates)
    
    # 查找员工ID
    staff = _find_staff_by_name(store, staff_name)
    if not staff:
        return _build_card("错误", f"未找到员工：{staff_name}")
    
    # 调用排班函数
    result = auto_reschedule_multiple_days(store, staff.id, actual_dates)
    
    if not result["ok"]:
        return _build_card("排班", result.get("reason", "无法安排"))
    
    # 构建建议消息
    suggestions_text = "\n".join([
        f"• {s['date']} {s['period']} → 建议让{s['replacement_name']}替班"
        for s in result["suggestions"]
    ])
    
    # 保存到session等待确认
    session.pending_action = "apply_multi_day_reschedule"
    session.pending_params = {"staff_id": staff.id, "suggestions": result["suggestions"]}
    session.state = SessionState.AWAITING_CONFIRMATION
    session.confirm_message = f"{staff_name}在以下时间有排班：\n{suggestions_text}\n\n确认吗？或告诉我你想让谁来"
    
    return _build_card("排班建议", session.confirm_message)


async def _handle_record_revenue(parsed, store):
    from backend.modules.accounting import record_platform_revenue
    from backend.bot.feishu import _build_card
    from datetime import datetime
    
    revenues = parsed.params.get("revenues", {})
    date = datetime.now().strftime("%Y-%m-%d")
    
    record_platform_revenue(store, date, revenues)
    
    total = sum(revenues.values())
    detail = "\n".join([f"• {p}：{a}元" for p, a in revenues.items()])
    
    return _build_card("记账成功", f"已记录 {date} 收入：\n{detail}\n总计：{total}元")


async def _handle_query_profit(parsed, store):
    from backend.modules.daily_report import calculate_daily_profit
    from backend.bot.feishu import _build_card
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
```

**验证：** 端到端测试

---

## 总结

**预计总时长：** 10小时  
**关键里程碑：**
1. 数据模型完成 (1h)
2. 后端API完成 (5h)
3. Bot集成完成 (4h)

**验证方式：**
- 单元测试覆盖率 > 80%
- 通过ngrok让老板试用3天
- 收集反馈决定第二阶段UI开发

**文档结束**
