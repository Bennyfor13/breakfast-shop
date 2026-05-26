# 早餐店助手功能增强设计文档

**日期：** 2026-05-22  
**版本：** v1.0  
**方案：** 渐进式实现（Backend-first + Progressive UI）

---

## 一、需求概述

### 1.1 背景
早餐店助手当前处于调试阶段，需要增强以下4个核心功能：
1. **智能排班** - 处理员工请假、临时调整
2. **局部排班修改** - 支持单日/单周/整周修改
3. **记账页面** - 多平台收入录入
4. **利润与成本追踪** - 每日利润、单品明细、原料消耗

### 1.2 实现策略
**第一阶段（本周）：** Backend API + 飞书Bot验证  
**第二阶段（下周）：** 根据使用频率决定哪些功能做网页UI

---

## 二、数据模型设计

### 2.1 平台收入记录
```python
class PlatformRevenue(BaseModel):
    """老板每日按平台录入的收入"""
    date: str  # "2026-05-22"
    platform: str  # "美团" | "饿了么" | "堂食" | "其他"
    amount: float  # 当日该平台总收入
    note: str = ""
```

### 2.2 每日利润报告
```python
class DailyProfitReport(BaseModel):
    """每日利润汇总"""
    date: str
    total_revenue: float  # 总收入（所有平台）
    total_cost: float  # 总成本（原料+房租+人工）
    net_profit: float  # 净利润
    item_breakdown: list[dict]  # 单品利润明细
    ingredient_consumption: dict[str, float]  # 理论原料消耗
```

### 2.3 实际消耗记录
```python
class ActualConsumption(BaseModel):
    """实际原料消耗 vs 理论消耗"""
    date: str
    ingredient_name: str
    theoretical: float  # 理论消耗（BOM计算）
    actual: float  # 实际消耗（老板录入）
    difference: float  # actual - theoretical
    note: str = ""
```

### 2.4 月度固定成本
```python
class MonthlyFixedCost(BaseModel):
    """月度固定成本配置"""
    month: str  # "2026-05"
    rent: float  # 月租金
    utilities: float  # 水电费
    other: float  # 其他固定支出
    
    def daily_cost(self, days_in_month: int = 30) -> float:
        """计算日均固定成本"""
        return (self.rent + self.utilities + self.other) / days_in_month
```

---

## 三、Backend API设计

### 3.1 排班增强模块 (`backend/modules/scheduling.py`)

#### 3.1.1 多天请假处理
```python
def auto_reschedule_multiple_days(
    store: AbstractStore, 
    staff_id: str, 
    dates: list[str]
) -> dict:
    """
    处理某人多天请假，自动找替班人
    
    Args:
        staff_id: 请假员工ID
        dates: 请假日期列表 ["2026-05-21", "2026-05-23"]
    
    Returns:
        {
            "ok": True,
            "suggestions": [
                {
                    "date": "2026-05-21",
                    "period": "早班",
                    "original": "staff_001",
                    "replacement_id": "staff_002",
                    "replacement_name": "小李"
                },
                ...
            ]
        }
    
    逻辑：
    1. 遍历每个日期，找出该员工的所有班次
    2. 对每个班次调用现有的 find_replacement()
    3. 优先选择本周班次少的员工
    4. 返回建议方案，等待确认
    """
```

#### 3.1.2 整周取消某人
```python
def cancel_staff_for_week(
    store: AbstractStore,
    staff_id: str,
    week_start: str,
    period_filter: str | None = None  # "早班" | "晚班" | None(全部)
) -> dict:
    """
    取消某人整周（或整周某时段）的班次，自动找替班
    
    Args:
        staff_id: 要取消的员工ID
        week_start: 周起始日期 "2026-05-18"
        period_filter: 可选，只取消特定时段
    
    Returns:
        {
            "ok": True,
            "affected_shifts": 6,
            "replacements": [...]  # 同 auto_reschedule_multiple_days
        }
    
    逻辑：
    1. 获取该员工本周所有班次
    2. 如果指定 period_filter，只处理该时段
    3. 对每个班次找替班人
    4. 返回建议方案
    """
```

### 3.2 记账模块 (`backend/modules/accounting.py` - 新建)

#### 3.2.1 记录平台收入
```python
def record_platform_revenue(
    store: AbstractStore,
    date: str,
    revenues: dict[str, float]
) -> bool:
    """
    记录当日各平台收入
    
    Args:
        date: "2026-05-22"
        revenues: {"美团": 500, "饿了么": 300, "堂食": 200}
    
    Returns:
        True if success
    
    逻辑：
    1. 遍历 revenues，为每个平台创建 PlatformRevenue 记录
    2. 保存到 store
    """
```

#### 3.2.2 获取每日收入
```python
def get_daily_revenue(
    store: AbstractStore,
    date: str
) -> dict:
    """
    获取某日总收入及平台明细
    
    Returns:
        {
            "date": "2026-05-22",
            "total": 1000,
            "by_platform": {"美团": 500, "饿了么": 300, "堂食": 200}
        }
    """
```

### 3.3 利润追踪模块 (`backend/modules/daily_report.py` - 新建)

#### 3.3.1 计算每日利润
```python
def calculate_daily_profit(
    store: AbstractStore,
    date: str
) -> DailyProfitReport:
    """
    计算某日利润
    
    逻辑：
    1. 从 get_daily_revenue() 获取总收入
    2. 从 SalesRecord 获取当日销量
    3. 计算成本：
       - 原料成本：每个菜品调用 pricing.calculate_item_cost() 的 raw_material 部分
       - 人工成本：从 AttendanceLog 获取当日实际出勤人数 × 日薪
       - 固定成本：从 MonthlyFixedCost 获取日均房租/水电
    4. 汇总：净利润 = 总收入 - (原料成本 + 人工成本 + 固定成本)
    5. 生成单品明细和原料消耗
    """
```

#### 3.3.2 获取原料消耗
```python
def get_ingredient_consumption(
    store: AbstractStore,
    date: str
) -> dict[str, float]:
    """
    计算某日理论原料消耗
    
    逻辑：
    1. 从 SalesRecord 获取当日每个菜品的销量
    2. 根据每个菜品的 BOM 计算原料用量
    3. 汇总返回：{"面粉": 5200, "猪肉": 2800, ...}  # 单位：克
    """
```

#### 3.3.3 记录实际消耗
```python
def record_actual_consumption(
    store: AbstractStore,
    date: str,
    actual: dict[str, float]
) -> dict:
    """
    记录实际原料消耗，并计算与理论值的差异
    
    Args:
        actual: {"面粉": 6000, "猪肉": 3000}  # 单位：克
    
    Returns:
        {
            "date": "2026-05-22",
            "differences": [
                {"ingredient": "面粉", "theoretical": 5200, "actual": 6000, 
                 "difference": 800, "percentage": 15.4},
                ...
            ]
        }
    
    逻辑：
    1. 调用 get_ingredient_consumption() 获取理论值
    2. 对比实际值，计算差异
    3. 保存 ActualConsumption 记录
    """
```

---

## 四、飞书Bot对话流程

### 4.1 场景1：多天请假处理

**触发语句：** "小王这周三、周五都没空"

**对话流程：**
```
用户: "小王这周三、周五都没空"
  ↓
Bot解析: staff="小王", dates=["2026-05-21", "2026-05-23"]
  ↓
调用: auto_reschedule_multiple_days()
  ↓
Bot回复:
"小王在以下时间有排班：
• 周三早班 → 建议让小李替班
• 周五早班 → 建议让小张替班
• 周五晚班 → 建议让小陈替班

回复「确认」接受建议
或者告诉我你想让谁来，例如：「周三让小赵」"
  ↓
【分支A：接受建议】
用户: "确认"
Bot: "已完成替班安排"

【分支B：自定义人选】
用户: "周三让小赵，周五晚班让小孙"
  ↓
Bot更新建议:
"好的，更新后的安排：
• 周三早班 → 小赵
• 周五早班 → 小张（建议）
• 周五晚班 → 小孙

确认吗？"
  ↓
用户: "确认"
Bot: "已完成替班安排"
```

### 4.2 场景2：整周取消某人

**触发语句：** 
- "小李这周都不来了，为我排班"
- "小李这周早班都不来了，为我排班"

**对话流程：**
```
用户: "小李这周都不来了，为我排班"
  ↓
Bot解析: staff="小李", scope="整周"
  ↓
调用: cancel_staff_for_week(staff_id, week_start, period_filter=None)
  ↓
Bot回复:
"小李本周共有 6 个班次：
• 周一早班 → 建议让小张替
• 周三早班 → 建议让小陈替
• 周三晚班 → 建议让小孙替
• 周五早班 → 建议让小赵替
• 周六早班 → 建议让小王替
• 周日晚班 → 建议让小刘替

确认吗？或告诉我你想让谁来"
```

### 4.3 场景3：记账与利润查询

#### 4.3.1 录入收入
```
用户: "今天美团500，饿了么300，堂食200"
  ↓
Bot解析: date=今天, revenues={"美团":500, "饿了么":300, "堂食":200}
  ↓
调用: record_platform_revenue()
  ↓
Bot回复:
"已记录 2026-05-22 收入：
• 美团：500元
• 饿了么：300元
• 堂食：200元
总计：1000元"
```

#### 4.3.2 查询利润
```
用户: "今天赚了多少"
  ↓
调用: calculate_daily_profit()
  ↓
Bot回复:
"2026-05-22 利润报告：
💰 总收入：1000元
💸 总成本：450元（原料280 + 房租100 + 人工70）
✅ 净利润：550元

单品明细：
• 包子：卖50份，赚150元
• 豆浆：卖80份，赚200元
• 油条：卖60份，赚200元"
```

#### 4.3.3 查询原料消耗 + 录入实际消耗
```
用户: "今天用了多少原料"
  ↓
调用: get_ingredient_consumption()
  ↓
Bot回复:
"2026-05-22 理论消耗（根据销量计算）：
• 面粉：5.2kg
• 猪肉：2.8kg
• 黄豆：3.5kg

实际消耗是否一致？
回复「一致」或告诉我实际用量
例如：「面粉6kg，猪肉3kg」"
  ↓
【分支A：一致】
用户: "一致"
Bot: "已记录，无差异"

【分支B：有差异】
用户: "面粉6kg，猪肉3kg"
  ↓
调用: record_actual_consumption()
  ↓
Bot:
"已记录实际消耗，差异如下：
• 面粉：理论5.2kg，实际6kg，多用0.8kg ⚠️
• 猪肉：理论2.8kg，实际3kg，多用0.2kg ⚠️
• 黄豆：理论3.5kg，实际3.5kg（未录入，按理论值）

提示：持续差异可能需要调整配方或检查浪费"
```

---

## 五、实现计划

### 5.1 第一阶段：Backend API + Bot验证（本周）

**优先级顺序：**

1. **数据模型** (1小时)
   - 在 `backend/data/models.py` 添加 3 个新模型
   - 在 `backend/data/interface.py` 和 `mock_store.py` 添加对应的存储接口

2. **排班增强** (2小时)
   - 实现 `auto_reschedule_multiple_days()`
   - 实现 `cancel_staff_for_week()`
   - 单元测试

3. **记账模块** (1小时)
   - 新建 `backend/modules/accounting.py`
   - 实现 `record_platform_revenue()` 和 `get_daily_revenue()`
   - 单元测试

4. **利润追踪模块** (2小时)
   - 新建 `backend/modules/daily_report.py`
   - 实现 3 个函数
   - 单元测试

5. **Bot集成** (4小时)
   - 在 `backend/bot/llm_nlu.py` 添加新意图识别
     - 使用LLM结构化输出解析日期：`{staff_name: "小王", dates: ["2026-05-21", "2026-05-23"]}`
     - 解析平台收入：`{revenues: {"美团": 500, "饿了么": 300}}`
     - 解析原料消耗：`{ingredients: {"面粉": 6000, "猪肉": 3000}}`
   - 在 `backend/bot/dispatcher.py` 添加新场景处理
   - 更新 `backend/bot/session.py` 支持多轮对话
   - 集成测试

**验证方式：**
- 通过 ngrok 让老板在飞书上试用 3 天
- 收集反馈：哪些功能高频使用，哪些交互不顺畅

### 5.2 第二阶段：选择性UI开发（下周）

**根据第一阶段反馈决定：**

| 功能 | 如果高频使用 | 如果低频使用 |
|------|------------|------------|
| 收入录入 | 做网页表单（3个输入框） | 继续用Bot |
| 利润查看 | 做图表页面 | 继续用Bot |
| 排班调整 | 做可视化排班表 | 继续用Bot |

**预估工作量：**
- 单个简单表单页面：2小时
- 单个图表页面：3小时
- 可视化排班表：5小时

---

## 六、技术风险与注意事项

### 6.1 数据一致性
- **风险：** 平台收入总和 ≠ 实际销售记录总和
- **缓解：** Bot 在录入收入后，自动对比 SalesRecord，如果差异>10% 提醒老板

### 6.2 NLU解析准确性
- **风险：** "小王周三周五没空" 可能被解析错
- **缓解：** 解析后回显给用户确认，支持修正

### 6.3 替班逻辑公平性
- **风险：** 总是同一批人被分配替班
- **缓解：** 优先选择本周班次少的员工，记录替班次数

### 6.4 边界情况处理
- **找不到替班人：** 
  - Bot回复："无法找到合适的替班人选，建议：1) 调整其他员工的班次 2) 老板亲自顶班"
  - 返回当前所有员工的本周班次统计，供老板手动决策
- **部分平台收入录入：**
  - 允许老板只录入部分平台（如只录入"美团500"）
  - Bot提示："已记录美团500元，其他平台收入可稍后补充"
  - 利润计算时使用已录入的收入，标注"部分数据"
- **实际消耗只录入部分原料：**
  - 未录入的原料按理论值计算
  - 差异报告中标注"（未录入，按理论值）"

---

## 七、成功标准

### 7.1 功能完整性
- ✅ 支持多天请假自动找替班
- ✅ 支持整周取消某人
- ✅ 支持多平台收入录入
- ✅ 自动计算每日利润和原料消耗
- ✅ 支持实际消耗录入和差异追踪

### 7.2 用户体验
- ✅ Bot 响应时间 < 2秒
- ✅ 对话流程不超过 3 轮
- ✅ 老板能在 1 分钟内完成每日记账

### 7.3 可维护性
- ✅ 所有新函数有单元测试
- ✅ 代码复用现有模块（pricing, inventory）
- ✅ 清晰的错误提示

---

**文档结束**
