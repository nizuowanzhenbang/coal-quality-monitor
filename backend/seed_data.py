"""演示数据生成脚本"""
import random
import sys
import os
from datetime import datetime, timedelta

# 确保可以直接运行：python seed_data.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal, Base
from app.models.user import User, UserRole
from app.models.supplier import Supplier, SupplierStatus
from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.alert import QualityAlert

from app.services.quality_engine import QualityEngine
from app.services.supplier_scorer import SupplierScorer
from passlib.context import CryptContext

random.seed(42)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── 供应商数据 ──────────────────────────────────────────────────────────────────

SUPPLIERS = [
    {"name": "神华集团煤炭销售有限公司", "contact_person": "王建国", "contact_phone": "010-12345678",
     "coal_types": "大同煤,准格尔煤", "quality": "excellent"},
    {"name": "中煤能源集团有限公司", "contact_person": "李志远", "contact_phone": "010-87654321",
     "coal_types": "平朔煤,华亭煤", "quality": "good"},
    {"name": "伊泰集团有限公司", "contact_person": "张强", "contact_phone": "0477-8888888",
     "coal_types": "伊泰煤,鄂尔多斯煤", "quality": "good"},
    {"name": "陕西煤业化工集团", "contact_person": "赵明", "contact_phone": "029-99999999",
     "coal_types": "彬长煤,黄陵煤", "quality": "average"},
    {"name": "山西焦煤集团有限责任公司", "contact_person": "孙伟", "contact_phone": "0351-5555555",
     "coal_types": "焦煤,肥煤,瘦煤", "quality": "average"},
    {"name": "国电电力发展股份有限公司", "contact_person": "周磊", "contact_phone": "010-66666666",
     "coal_types": "混煤,贫煤", "quality": "poor"},
    {"name": "兖矿能源集团股份有限公司", "contact_person": "吴建华", "contact_phone": "0537-7777777",
     "coal_types": "兖州煤,济宁煤", "quality": "poor"},
    {"name": "淮南矿业集团有限责任公司", "contact_person": "郑国庆", "contact_phone": "0554-4444444",
     "coal_types": "淮南煤,淮北煤", "quality": "bad"},
]

# 煤种标准质量区间（用于生成合理化验数据）
COAL_QUALITY_PROFILES = {
    "大同煤": {"cal": (5800, 6200), "ash": (8, 14), "sulfur": (0.4, 0.8), "moisture": (8, 14), "volatile": (28, 35)},
    "准格尔煤": {"cal": (5500, 5900), "ash": (12, 18), "sulfur": (0.5, 1.0), "moisture": (10, 16), "volatile": (30, 38)},
    "平朔煤": {"cal": (5600, 6000), "ash": (10, 16), "sulfur": (0.6, 1.2), "moisture": (9, 15), "volatile": (29, 36)},
    "default": {"cal": (5200, 5800), "ash": (14, 22), "sulfur": (0.6, 1.5), "moisture": (10, 18), "volatile": (25, 35)},
}


def _rand(lo, hi, decimal=2):
    return round(random.uniform(lo, hi), decimal)


def _get_profile(coal_type: str) -> dict:
    for k in COAL_QUALITY_PROFILES:
        if k in (coal_type or ""):
            return COAL_QUALITY_PROFILES[k]
    return COAL_QUALITY_PROFILES["default"]


def _generate_port_values(profile: dict) -> dict:
    """生成港口化验数据（基准值）"""
    cal = _rand(*profile["cal"], 0)
    return {
        "calorific_value_net": cal,
        "calorific_value_gross": round(cal * 1.045, 0),
        "ash_content": _rand(*profile["ash"]),
        "sulfur_content": _rand(*profile["sulfur"], 3),
        "moisture_total": _rand(*profile["moisture"]),
        "moisture_inherent": _rand(1.5, 4.0),
        "volatile_matter": _rand(*profile["volatile"]),
        "fixed_carbon": _rand(45, 65),
    }


def _generate_factory_values(port: dict, quality_level: str) -> dict:
    """
    基于港口值生成入厂化验数据
    - excellent/good: 偏差在阈值内
    - average: 偶发超阈值
    - poor/bad: 频繁超阈值，甚至严重偏差
    """
    bias_map = {
        "excellent": (0.002, 0.005),   # 热值亏损率区间
        "good": (0.003, 0.012),
        "average": (0.008, 0.025),
        "poor": (0.015, 0.035),
        "bad": (0.025, 0.060),
    }
    lo, hi = bias_map.get(quality_level, (0.005, 0.015))
    cal_loss_rate = _rand(lo, hi, 4)

    cal_port = port["calorific_value_net"]
    cal_factory = round(cal_port * (1 - cal_loss_rate), 0)

    # 灰分偏差（正方向，入厂 > 港口）
    ash_bias_map = {
        "excellent": (0.0, 0.3), "good": (0.0, 0.7),
        "average": (0.2, 1.2), "poor": (0.5, 2.0), "bad": (1.0, 3.5),
    }
    ash_lo, ash_hi = ash_bias_map.get(quality_level, (0.0, 0.5))
    ash_dev = _rand(ash_lo, ash_hi)

    # 硫分偏差
    sulf_bias_map = {
        "excellent": (0.000, 0.030), "good": (0.010, 0.060),
        "average": (0.030, 0.100), "poor": (0.060, 0.180), "bad": (0.100, 0.350),
    }
    sl, sh = sulf_bias_map.get(quality_level, (0.0, 0.05))
    sulf_dev = _rand(sl, sh, 3)

    # 水分偏差
    moist_bias_map = {
        "excellent": (0.0, 0.5), "good": (0.0, 0.8),
        "average": (0.3, 1.5), "poor": (0.8, 2.5), "bad": (1.5, 4.0),
    }
    ml, mh = moist_bias_map.get(quality_level, (0.0, 1.0))
    moist_dev = _rand(ml, mh)

    return {
        "calorific_value_net": cal_factory,
        "calorific_value_gross": round(cal_factory * 1.045, 0),
        "ash_content": round(port["ash_content"] + ash_dev, 2),
        "sulfur_content": round(port["sulfur_content"] + sulf_dev, 3),
        "moisture_total": round(port["moisture_total"] + moist_dev, 2),
        "moisture_inherent": round(port["moisture_inherent"] + _rand(0, 0.3), 2),
        "volatile_matter": round(port["volatile_matter"] + _rand(-1, 1), 2),
        "fixed_carbon": round(port["fixed_carbon"] + _rand(-2, 2), 2),
    }


def run():
    print("=" * 60)
    print("开始生成煤质化验演示数据")
    print("=" * 60)

    # 建表
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 清理旧数据
        db.query(QualityAlert).delete()
        db.query(QualityTest).delete()
        db.query(CoalBatch).delete()
        db.query(Supplier).delete()
        db.query(User).filter(User.username != "admin").delete()
        db.commit()

        # 创建默认管理员
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin",
                hashed_password=pwd_context.hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            ))
        # 创建操作员
        if not db.query(User).filter(User.username == "operator").first():
            db.add(User(
                username="operator",
                hashed_password=pwd_context.hash("operator123"),
                role=UserRole.OPERATOR,
                is_active=True,
            ))
        db.commit()
        print("[1/5] 用户账户已就绪（admin / operator）")

        # 创建供应商
        supplier_objs = []
        for s_data in SUPPLIERS:
            quality = s_data.pop("quality")
            supplier = Supplier(**s_data)
            db.add(supplier)
            db.flush()
            supplier_objs.append((supplier, quality))
        db.commit()
        print(f"[2/5] 已创建 {len(supplier_objs)} 个供应商")

        # 港口列表
        ports = ["曹妃甸港", "秦皇岛港", "天津港", "青岛港", "连云港", "日照港"]
        plants = ["华能济南电厂", "国电泰安电厂", "大唐淮南电厂", "华电南京电厂", "中电投淮北电厂"]
        coal_type_map = {
            "神华集团煤炭销售有限公司": "大同煤",
            "中煤能源集团有限公司": "平朔煤",
            "伊泰集团有限公司": "准格尔煤",
        }

        # 生成50个批次
        total_batches = 50
        batch_counter = 0
        alert_counter = 0
        engine_svc = QualityEngine()

        print(f"[3/5] 开始生成 {total_batches} 个批次...")

        for i in range(total_batches):
            # 随机分配供应商（低质量供应商稍多，模拟现实）
            supplier, quality = random.choice(supplier_objs)
            coal_types_raw = supplier.coal_types or "混煤"
            coal_type = random.choice(coal_types_raw.split(","))
            profile = _get_profile(coal_type)

            # 合同指标（比实际值宽松一些）
            contract_cal = _rand(*profile["cal"], 0) - random.choice([0, 100, 200])
            contract_ash = _rand(*profile["ash"]) + _rand(1, 3)
            contract_sulfur = _rand(*profile["sulfur"], 2) + _rand(0.05, 0.2, 2)
            contract_moisture = _rand(*profile["moisture"]) + _rand(1, 3)

            arrival_date = datetime.utcnow() - timedelta(days=random.randint(0, 90))
            batch_number = f"CQ{arrival_date.strftime('%Y%m')}{i+1:04d}"

            batch = CoalBatch(
                batch_number=batch_number,
                supplier_id=supplier.id,
                coal_type=coal_type,
                departure_port=random.choice(ports),
                arrival_plant=random.choice(plants),
                contract_quantity=_rand(5000, 30000, 0),
                actual_quantity=_rand(4900, 30500, 0),
                contract_calorific_value=contract_cal,
                contract_ash_max=contract_ash,
                contract_sulfur_max=contract_sulfur,
                contract_moisture_max=contract_moisture,
                status=BatchStatus.PENDING,
                arrival_date=arrival_date,
                created_at=arrival_date,
            )
            db.add(batch)
            db.flush()

            # 港口化验
            port_values = _generate_port_values(profile)
            port_test = QualityTest(
                batch_id=batch.id,
                test_type=TestType.PORT,
                test_org="中国煤炭质量监督检验中心",
                test_time=arrival_date - timedelta(days=random.randint(3, 10)),
                report_number=f"PORT{batch_number}",
                **port_values,
            )
            db.add(port_test)

            # 入厂化验
            factory_values = _generate_factory_values(port_values, quality)
            factory_test = QualityTest(
                batch_id=batch.id,
                test_type=TestType.FACTORY,
                test_org="到厂自检实验室",
                test_time=arrival_date + timedelta(days=random.randint(1, 3)),
                report_number=f"FACT{batch_number}",
                **factory_values,
            )
            db.add(factory_test)
            batch.status = BatchStatus.PARTIAL
            db.commit()

            # 重新加载 tests 关系，触发质量评估
            db.refresh(batch)
            # 手动加载 tests
            batch.tests  # 触发懒加载（非 joinedload）
            alerts_created = engine_svc.evaluate(batch, db)
            if alerts_created:
                alert_counter += len(alerts_created)
            batch_counter += 1

        db.commit()
        print(f"[4/5] 批次生成完成：{batch_counter} 个批次，{alert_counter} 条预警")

        # 重新计算所有供应商信用分
        scorer = SupplierScorer()
        for supplier, _ in supplier_objs:
            db.refresh(supplier)
            scorer.recalculate(supplier, db)
        print("[5/5] 供应商信用分已重新计算")

        # 打印摘要
        print("\n" + "=" * 60)
        print("数据摘要统计")
        print("=" * 60)

        from sqlalchemy import func
        from app.models.alert import Severity

        total = db.query(func.count(CoalBatch.id)).scalar()
        completed = db.query(func.count(CoalBatch.id)).filter(
            CoalBatch.status.in_([BatchStatus.COMPLETED, BatchStatus.ALERT, BatchStatus.SEVERE])
        ).scalar()
        alert_batches = db.query(func.count(CoalBatch.id)).filter(
            CoalBatch.status.in_([BatchStatus.ALERT, BatchStatus.SEVERE])
        ).scalar()
        total_alerts = db.query(func.count(QualityAlert.id)).scalar()
        severe_alerts = db.query(func.count(QualityAlert.id)).filter(
            QualityAlert.severity == Severity.SEVERE
        ).scalar()

        print(f"  总批次数：{total}")
        print(f"  已完成评估：{completed}")
        print(f"  存在预警批次：{alert_batches}（异常率 {alert_batches/completed*100:.1f}%）")
        print(f"  总预警数：{total_alerts}")
        print(f"  严重预警：{severe_alerts}")
        print()
        print("  供应商信用分排名：")
        suppliers_sorted = db.query(Supplier).order_by(Supplier.credit_score.desc()).all()
        for s in suppliers_sorted:
            print(f"    {s.name[:20]:20s}  {s.credit_score:6.1f}分  [{s.status}]")

        print()
        print("演示数据生成完成！")
        print("登录账户：admin / admin123 | operator / operator123")

    finally:
        db.close()


if __name__ == "__main__":
    run()
