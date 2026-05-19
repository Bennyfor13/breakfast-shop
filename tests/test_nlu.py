from backend.bot.nlu import parse_intent, Intent


def test_parse_schedule_query():
    result = parse_intent("明天排班")
    assert result.intent == Intent.SHOW_SCHEDULE


def test_parse_inventory_query():
    result = parse_intent("明天备料清单")
    assert result.intent == Intent.SHOW_INVENTORY


def test_parse_pricing_query():
    result = parse_intent("哪个菜品利润最高")
    assert result.intent == Intent.SHOW_PRICING


def test_parse_payroll_query():
    result = parse_intent("这个月工资")
    assert result.intent == Intent.SHOW_PAYROLL


def test_parse_add_staff():
    result = parse_intent("新增员工张三，后厨，早班80晚班60")
    assert result.intent == Intent.ADD_STAFF
    assert result.params["name"] == "张三"
    assert "后厨" in result.params["roles"]


def test_parse_add_menu():
    result = parse_intent("新增菜品鲜肉包，卖3块")
    assert result.intent == Intent.ADD_MENU
    assert result.params["name"] == "鲜肉包"
    assert result.params["price"] == 3.0


def test_parse_mark_absent():
    result = parse_intent("张三明天请假")
    assert result.intent == Intent.MARK_ABSENT
    assert "张三" in result.params.get("staff_name", "")


def test_parse_unknown():
    result = parse_intent("今天天气怎么样")
    assert result.intent == Intent.UNKNOWN
