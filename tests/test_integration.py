"""End-to-end: seed data → schedule → attendance → payroll."""
from backend.data.mock_store import MockStore
from backend.seed import seed
from backend.modules.scheduling import generate_weekly_schedule
from backend.modules.payroll import generate_monthly_payroll
from backend.modules.inventory import forecast_ingredient_needs
from backend.modules.pricing import analyze_all_items


def test_full_workflow():
    store = MockStore()
    seed(store)

    # 1. Generate schedule
    schedule = generate_weekly_schedule(store, "2026-05-18")
    store.save_shifts(schedule.shifts)
    assert len(schedule.shifts) > 0

    # 2. Mark attendance (one absence)
    from backend.data.models import AttendanceLog
    store.save_attendance(AttendanceLog(date="2026-05-20", absent=["s1"], substitute={}, overtime=[]))

    # 3. Calculate payroll
    payroll = generate_monthly_payroll(store, "2026-05")
    assert len(payroll) > 0
    s1_pay = next(p for p in payroll if p["staff_name"] == "张三")
    assert s1_pay["total"] > 0

    # 4. Forecast inventory
    needs = forecast_ingredient_needs(store, {"m1": 100, "m2": 50})
    assert "中筋面粉" in needs

    # 5. Pricing analysis
    sales = {"m1": 3000, "m2": 2000, "m3": 1500, "m4": 1000, "m5": 800}
    analysis = analyze_all_items(store, 5000, 15000, sum(sales.values()), sales)
    assert len(analysis) > 0
    assert analysis[0]["quadrant"] in ["明星", "金牛", "引流款", "考虑砍掉"]


def test_schedule_to_payroll_pipeline():
    """Direct pipeline: schedule generation → attendance marking → payroll calc."""
    store = MockStore()
    seed(store)

    schedule = generate_weekly_schedule(store, "2026-05-18")
    store.save_shifts(schedule.shifts)

    # Boss marks 张三 absent on Monday and Tuesday
    from backend.data.models import AttendanceLog, PerformanceScore
    store.save_attendance(AttendanceLog(date="2026-05-18", absent=["s1"], substitute={}, overtime=[]))
    store.save_attendance(AttendanceLog(date="2026-05-19", absent=["s1"], substitute={}, overtime=[]))

    # Boss rates performance
    store.save_performance(PerformanceScore(staff_id="s1", date=None, score=5.0))
    store.save_performance(PerformanceScore(staff_id="s2", date=None, score=3.5))

    # Monthly payroll
    payroll = generate_monthly_payroll(store, "2026-05")
    s1 = next(p for p in payroll if p["staff_name"] == "张三")
    s2 = next(p for p in payroll if p["staff_name"] == "李四")

    # s1 missed 2 days, should have fewer shifts than scheduled
    assert s1["morning_shifts"] >= 0
    # s2 had perfect attendance, bonus based on 3.5 score
    assert s2["performance_score"] == 3.5
    assert s2["performance_bonus"] > 0
