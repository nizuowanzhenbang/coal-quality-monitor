"""质量分析引擎单元测试"""
import pytest
from sqlalchemy.orm import Session

from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.alert import QualityAlert, AlertType, Severity
from app.models.supplier import Supplier
from app.services.quality_engine import QualityEngine
from app.services.supplier_scorer import SupplierScorer


def _make_test(
    db: Session,
    batch_id: int,
    test_type: TestType,
    *,
    calorific: float = None,
    ash: float = None,
    sulfur: float = None,
    moisture: float = None,
    volatile: float = None,
) -> QualityTest:
    """工厂函数：快速创建化验记录"""
    t = QualityTest(
        batch_id=batch_id,
        test_type=test_type,
        calorific_value_net=calorific,
        ash_content=ash,
        sulfur_content=sulfur,
        moisture_total=moisture,
        volatile_matter=volatile,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ─────────────────────────────────────────────────────────────────────────────
# 测试：正常化验无预警
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalCase:
    def test_no_alerts_when_within_thresholds(self, db_session, sample_batch):
        """港口和入厂数据接近，应无预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT,
                   calorific=6000, ash=15.0, sulfur=0.8, moisture=12.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY,
                   calorific=5990, ash=15.2, sulfur=0.82, moisture=12.3)  # 偏差极小

        engine = QualityEngine()
        # 手动加载 tests 关系
        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        alerts = engine.evaluate(batch, db_session)

        assert len(alerts) == 0
        assert batch.status == BatchStatus.COMPLETED
        assert batch.risk_score == 0.0

    def test_missing_factory_test_returns_empty(self, db_session, sample_batch):
        """仅有港口化验时，evaluate 返回空列表"""
        _make_test(db_session, sample_batch.id, TestType.PORT,
                   calorific=6000, ash=15.0, sulfur=0.8, moisture=12.0)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)
        assert alerts == []

    def test_missing_port_test_returns_empty(self, db_session, sample_batch):
        """仅有入厂化验时，evaluate 返回空列表"""
        _make_test(db_session, sample_batch.id, TestType.FACTORY,
                   calorific=5950, ash=16.0, sulfur=0.9, moisture=13.0)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)
        assert alerts == []


# ─────────────────────────────────────────────────────────────────────────────
# 测试：热值预警
# ─────────────────────────────────────────────────────────────────────────────

class TestCalorificAlerts:
    def test_calorific_general_alert(self, db_session, sample_batch):
        """热值亏损 1.5%（1% < x < 2%）→ 一般预警"""
        port_cal = 6000.0
        # 亏损 1.5%
        factory_cal = port_cal * (1 - 0.015)
        _make_test(db_session, sample_batch.id, TestType.PORT, calorific=port_cal)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, calorific=factory_cal)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        cal_alerts = [a for a in alerts if a.alert_type == AlertType.CALORIFIC_SHORTAGE]
        assert len(cal_alerts) == 1
        assert cal_alerts[0].severity == Severity.GENERAL
        assert batch.status == BatchStatus.ALERT

    def test_calorific_severe_alert(self, db_session, sample_batch):
        """热值亏损 2.5%（> 2%）→ 严重预警"""
        port_cal = 6000.0
        factory_cal = port_cal * (1 - 0.025)
        _make_test(db_session, sample_batch.id, TestType.PORT, calorific=port_cal)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, calorific=factory_cal)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        cal_alerts = [a for a in alerts if a.alert_type == AlertType.CALORIFIC_SHORTAGE]
        assert len(cal_alerts) == 1
        assert cal_alerts[0].severity == Severity.SEVERE
        assert batch.status == BatchStatus.SEVERE

    def test_calorific_no_alert_when_factory_higher(self, db_session, sample_batch):
        """入厂热值高于港口热值（不亏损）→ 无热值预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT, calorific=5900.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, calorific=5950.0)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        cal_alerts = [a for a in alerts if a.alert_type == AlertType.CALORIFIC_SHORTAGE]
        assert len(cal_alerts) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 测试：灰分预警
# ─────────────────────────────────────────────────────────────────────────────

class TestAshAlerts:
    def test_ash_general_alert(self, db_session, sample_batch):
        """灰分偏差 1.0%（0.8% < x < 1.5%）→ 一般预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT, ash=15.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, ash=16.0)  # 偏差 +1.0%

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        ash_alerts = [a for a in alerts if a.alert_type == AlertType.ASH_EXCESS]
        assert len(ash_alerts) == 1
        assert ash_alerts[0].severity == Severity.GENERAL

    def test_ash_severe_alert(self, db_session, sample_batch):
        """灰分偏差 2.0%（> 1.5%）→ 严重预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT, ash=15.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, ash=17.0)  # 偏差 +2.0%

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        ash_alerts = [a for a in alerts if a.alert_type == AlertType.ASH_EXCESS]
        assert len(ash_alerts) == 1
        assert ash_alerts[0].severity == Severity.SEVERE


# ─────────────────────────────────────────────────────────────────────────────
# 测试：硫分超合同
# ─────────────────────────────────────────────────────────────────────────────

class TestSulfurContractBreach:
    def test_sulfur_contract_general(self, db_session, sample_batch):
        """入厂硫分超合同上限 0.08%（0.05% < x < 0.10%）→ 合同违约一般预警"""
        # sample_batch.contract_sulfur_max = 1.0
        _make_test(db_session, sample_batch.id, TestType.PORT, sulfur=0.90)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, sulfur=1.08)  # 超合同 0.08%

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        contract_alerts = [a for a in alerts if a.alert_type == AlertType.CONTRACT_SULFUR_BREACH]
        assert len(contract_alerts) == 1
        assert contract_alerts[0].severity == Severity.GENERAL

    def test_sulfur_contract_severe(self, db_session, sample_batch):
        """入厂硫分超合同上限 0.15%（> 0.10%）→ 合同违约严重预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT, sulfur=0.90)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, sulfur=1.15)  # 超合同 0.15%

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        contract_alerts = [a for a in alerts if a.alert_type == AlertType.CONTRACT_SULFUR_BREACH]
        assert len(contract_alerts) == 1
        assert contract_alerts[0].severity == Severity.SEVERE


# ─────────────────────────────────────────────────────────────────────────────
# 测试：综合预警（3项指标同时偏差）
# ─────────────────────────────────────────────────────────────────────────────

class TestComprehensiveAlert:
    def test_comprehensive_alert_triggered(self, db_session, sample_batch):
        """热值/灰分/硫分/水分四项同时偏差 → 触发综合预警"""
        _make_test(
            db_session, sample_batch.id, TestType.PORT,
            calorific=6000, ash=15.0, sulfur=0.80, moisture=12.0,
        )
        _make_test(
            db_session, sample_batch.id, TestType.FACTORY,
            calorific=5000,   # 亏损 16.7%（严重）
            ash=17.5,         # 偏差 +2.5%（严重）
            sulfur=1.0,       # 偏差 +0.2%（严重）
            moisture=14.5,    # 偏差 +2.5%（严重）
        )

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        comp_alerts = [a for a in alerts if a.alert_type == AlertType.COMPREHENSIVE]
        assert len(comp_alerts) == 1
        assert comp_alerts[0].severity == Severity.SEVERE

        # 批次状态应为 SEVERE
        assert batch.status == BatchStatus.SEVERE

    def test_comprehensive_not_triggered_with_two_indicators(self, db_session, sample_batch):
        """仅2项指标偏差 → 不触发综合预警"""
        _make_test(
            db_session, sample_batch.id, TestType.PORT,
            calorific=6000, ash=15.0, sulfur=0.80, moisture=12.0,
        )
        _make_test(
            db_session, sample_batch.id, TestType.FACTORY,
            calorific=5700,   # 亏损 5%（严重）
            ash=17.0,         # 偏差 +2.0%（严重）
            sulfur=0.85,      # 偏差 +0.05%（未超阈值）
            moisture=12.5,    # 偏差 +0.5%（未超阈值）
        )

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)

        comp_alerts = [a for a in alerts if a.alert_type == AlertType.COMPREHENSIVE]
        assert len(comp_alerts) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 测试：供应商评分
# ─────────────────────────────────────────────────────────────────────────────

class TestSupplierScorer:
    def _create_batch_with_alerts(
        self, db: Session, supplier: Supplier, batch_number: str,
        has_severe: bool = False, has_comprehensive: bool = False
    ) -> CoalBatch:
        """创建带预警的批次"""
        from app.models.batch import CoalBatch, BatchStatus
        from app.models.alert import QualityAlert, AlertType, Severity, AlertStatus

        status = BatchStatus.SEVERE if (has_severe or has_comprehensive) else BatchStatus.ALERT
        batch = CoalBatch(
            batch_number=batch_number,
            supplier_id=supplier.id,
            status=status,
        )
        db.add(batch)
        db.flush()

        if has_comprehensive:
            db.add(QualityAlert(
                batch_id=batch.id,
                alert_type=AlertType.COMPREHENSIVE,
                severity=Severity.SEVERE,
                description="综合异常",
                threshold_value=3.0,
                status=AlertStatus.PENDING,
            ))
        elif has_severe:
            db.add(QualityAlert(
                batch_id=batch.id,
                alert_type=AlertType.CALORIFIC_SHORTAGE,
                severity=Severity.SEVERE,
                description="严重热值亏损",
                threshold_value=0.02,
                status=AlertStatus.PENDING,
            ))
        else:
            db.add(QualityAlert(
                batch_id=batch.id,
                alert_type=AlertType.ASH_EXCESS,
                severity=Severity.GENERAL,
                description="灰分偏高",
                threshold_value=0.8,
                status=AlertStatus.PENDING,
            ))
        db.commit()
        return batch

    def test_score_decreases_with_alerts(self, db_session, sample_supplier):
        """有预警批次导致信用分下降"""
        self._create_batch_with_alerts(db_session, sample_supplier, "SC-001", has_severe=False)

        scorer = SupplierScorer()
        score = scorer.recalculate(sample_supplier, db_session)
        assert score < 100.0
        assert score == 97.0  # 一般预警 -3分

    def test_severe_alert_deducts_more(self, db_session, sample_supplier):
        """严重预警比一般预警扣更多分"""
        self._create_batch_with_alerts(db_session, sample_supplier, "SC-002", has_severe=True)

        scorer = SupplierScorer()
        score = scorer.recalculate(sample_supplier, db_session)
        assert score == 90.0  # 严重预警 -10分

    def test_comprehensive_deducts_most(self, db_session, sample_supplier):
        """综合异常扣分最多"""
        self._create_batch_with_alerts(db_session, sample_supplier, "SC-003", has_comprehensive=True)

        scorer = SupplierScorer()
        score = scorer.recalculate(sample_supplier, db_session)
        assert score == 85.0  # 综合异常 -15分

    def test_score_clamped_to_zero(self, db_session, sample_supplier):
        """多个异常批次分数下限为0"""
        for i in range(10):
            self._create_batch_with_alerts(
                db_session, sample_supplier, f"SC-CLAMP-{i}", has_comprehensive=True
            )

        scorer = SupplierScorer()
        score = scorer.recalculate(sample_supplier, db_session)
        assert score == 0.0

    def test_no_batches_keeps_score(self, db_session, sample_supplier):
        """无历史批次时，信用分保持不变"""
        original_score = sample_supplier.credit_score
        scorer = SupplierScorer()
        score = scorer.recalculate(sample_supplier, db_session)
        assert score == original_score


# ─────────────────────────────────────────────────────────────────────────────
# 测试：边界情况（None 值安全处理）
# ─────────────────────────────────────────────────────────────────────────────

class TestNullSafety:
    def test_none_calorific_no_crash(self, db_session, sample_batch):
        """热值为 None 时不崩溃"""
        _make_test(db_session, sample_batch.id, TestType.PORT,
                   calorific=None, ash=15.0, sulfur=0.8, moisture=12.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY,
                   calorific=None, ash=15.5, sulfur=0.85, moisture=12.5)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        # 不应抛出异常
        alerts = engine.evaluate(batch, db_session)
        # 热值 None 则不生成热值预警
        cal_alerts = [a for a in alerts if a.alert_type == AlertType.CALORIFIC_SHORTAGE]
        assert len(cal_alerts) == 0

    def test_none_ash_no_crash(self, db_session, sample_batch):
        """灰分为 None 时不崩溃"""
        _make_test(db_session, sample_batch.id, TestType.PORT, calorific=6000)
        _make_test(db_session, sample_batch.id, TestType.FACTORY, calorific=5980)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)
        ash_alerts = [a for a in alerts if a.alert_type == AlertType.ASH_EXCESS]
        assert len(ash_alerts) == 0

    def test_all_none_no_crash(self, db_session, sample_batch):
        """所有指标均为 None 时不崩溃，无预警"""
        _make_test(db_session, sample_batch.id, TestType.PORT)
        _make_test(db_session, sample_batch.id, TestType.FACTORY)

        from sqlalchemy.orm import joinedload
        batch = (
            db_session.query(CoalBatch)
            .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
            .filter(CoalBatch.id == sample_batch.id)
            .first()
        )
        engine = QualityEngine()
        alerts = engine.evaluate(batch, db_session)
        assert len(alerts) == 0
        assert batch.status == BatchStatus.COMPLETED

    def test_idempotent_evaluate(self, db_session, sample_batch):
        """重复调用 evaluate 结果幂等（旧预警被替换）"""
        _make_test(db_session, sample_batch.id, TestType.PORT,
                   calorific=6000, ash=15.0, sulfur=0.8, moisture=12.0)
        _make_test(db_session, sample_batch.id, TestType.FACTORY,
                   calorific=5820,  # 亏损 3%（严重）
                   ash=16.5, sulfur=0.9, moisture=13.0)

        from sqlalchemy.orm import joinedload
        engine = QualityEngine()

        def _load():
            return (
                db_session.query(CoalBatch)
                .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
                .filter(CoalBatch.id == sample_batch.id)
                .first()
            )

        batch1 = _load()
        alerts1 = engine.evaluate(batch1, db_session)

        batch2 = _load()
        alerts2 = engine.evaluate(batch2, db_session)

        # 两次调用结果数量一致
        assert len(alerts1) == len(alerts2)

        # 数据库中仅有一份预警（第二次替换第一次）
        total_in_db = db_session.query(QualityAlert).filter(
            QualityAlert.batch_id == sample_batch.id
        ).count()
        assert total_in_db == len(alerts2)
