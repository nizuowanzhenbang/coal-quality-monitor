"""质量分析引擎"""
from dataclasses import dataclass
from typing import List, Optional, Sequence
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.alert import QualityAlert, AlertType, Severity
from app.config import settings


@dataclass
class AlertData:
    alert_type: AlertType
    severity: Severity
    description: str
    port_value: Optional[float]
    factory_value: Optional[float]
    deviation: Optional[float]
    deviation_rate: Optional[float]
    threshold_value: float


class QualityEngine:
    QUALITY_ALERT_TYPES = (
        AlertType.CALORIFIC_SHORTAGE,
        AlertType.ASH_EXCESS,
        AlertType.SULFUR_EXCESS,
        AlertType.MOISTURE_EXCESS,
        AlertType.CONTRACT_CAL_BREACH,
        AlertType.CONTRACT_ASH_BREACH,
        AlertType.CONTRACT_SULFUR_BREACH,
        AlertType.COMPREHENSIVE,
    )
    # 各预警类型权重
    TYPE_WEIGHTS = {
        AlertType.CALORIFIC_SHORTAGE: 0.40,
        AlertType.ASH_EXCESS: 0.25,
        AlertType.SULFUR_EXCESS: 0.20,
        AlertType.MOISTURE_EXCESS: 0.10,
        AlertType.CONTRACT_CAL_BREACH: 0.40,
        AlertType.CONTRACT_ASH_BREACH: 0.25,
        AlertType.CONTRACT_SULFUR_BREACH: 0.20,
        AlertType.COMPREHENSIVE: 0.05,
        AlertType.TRANSPORT_WEIGHT: 0.35,
        AlertType.TRANSPORT_TIME: 0.15,
        AlertType.TRANSPORT_SEAL: 0.30,
    }
    # 严重程度系数
    SEVERITY_FACTORS = {Severity.GENERAL: 1.0, Severity.SEVERE: 2.0}

    def evaluate(self, batch: CoalBatch, db: Session) -> List[QualityAlert]:
        """
        对批次执行质量评估：
        1. 找到港口和入厂两份化验记录
        2. 逐指标比对，生成预警数据
        3. 检查综合异常
        4. 仅替换本引擎的质量预警，保留运输预警及其处理记录
        5. 按全部预警更新批次状态和风险评分
        """
        port_test = None
        factory_test = None
        for t in batch.tests:
            if t.test_type == TestType.PORT:
                port_test = t
            elif t.test_type == TestType.FACTORY:
                factory_test = t

        if not port_test or not factory_test:
            return []

        all_data: List[AlertData] = []
        all_data.extend(self._check_calorific(port_test, factory_test, batch))
        all_data.extend(self._check_ash(port_test, factory_test, batch))
        all_data.extend(self._check_sulfur(port_test, factory_test, batch))
        all_data.extend(self._check_moisture(port_test, factory_test))
        all_data.extend(self._check_comprehensive(all_data))

        db.query(QualityAlert).filter(
            QualityAlert.batch_id == batch.id,
            QualityAlert.alert_type.in_(self.QUALITY_ALERT_TYPES),
        ).delete(synchronize_session="fetch")

        created: List[QualityAlert] = []
        for d in all_data:
            a = QualityAlert(
                batch_id=batch.id,
                alert_type=d.alert_type,
                severity=d.severity,
                description=d.description,
                port_value=d.port_value,
                factory_value=d.factory_value,
                deviation=d.deviation,
                deviation_rate=d.deviation_rate,
                threshold_value=d.threshold_value,
            )
            db.add(a)
            created.append(a)

        # autoflush may be disabled; include newly generated and retained rows.
        db.flush()
        combined = db.query(QualityAlert).filter(QualityAlert.batch_id == batch.id).all()
        if combined:
            has_severe = any(a.severity == Severity.SEVERE for a in combined)
            batch.status = BatchStatus.SEVERE if has_severe else BatchStatus.ALERT
        else:
            batch.status = BatchStatus.COMPLETED

        batch.alert_count = len(combined)
        batch.risk_score = round(self._compute_risk_score(combined), 2)
        db.commit()

        for a in created:
            db.refresh(a)

        # 异步广播新预警到所有 WebSocket 客户端
        if created:
            self._broadcast(batch, created)

        return created

    @staticmethod
    def _broadcast(batch: CoalBatch, alerts: List[QualityAlert]) -> None:
        """将新预警推送给所有在线客户端（失败静默）"""
        try:
            import asyncio
            from app.api.ws import broadcast
            loop = asyncio.get_event_loop()
            for alert in alerts:
                payload = {
                    "type": "new_alert",
                    "data": {
                        "id": alert.id,
                        "batch_id": alert.batch_id,
                        "batch_number": batch.batch_number,
                        "alert_type": alert.alert_type.value,
                        "severity": alert.severity.value,
                        "description": alert.description,
                        "created_at": alert.created_at.isoformat() if alert.created_at else None,
                    },
                }
                if loop.is_running():
                    asyncio.ensure_future(broadcast(payload))
        except Exception:
            pass

    def _check_calorific(
        self, port: QualityTest, factory: QualityTest, batch: CoalBatch
    ) -> List[AlertData]:
        """检查热值偏差和合同违约"""
        results = []
        pv = port.calorific_value_net
        fv = factory.calorific_value_net
        if pv and fv and pv > 0:
            deviation = pv - fv        # 正值 = 入厂低于港口（亏损）
            rate = deviation / pv
            if rate > settings.CALORIFIC_SEVERE_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.CALORIFIC_SHORTAGE,
                    severity=Severity.SEVERE,
                    description=(
                        f"热值严重亏损！港口 {pv:.0f} kcal/kg，入厂 {fv:.0f} kcal/kg，"
                        f"亏损率 {rate*100:.2f}%（阈值 {settings.CALORIFIC_SEVERE_THRESHOLD*100:.0f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation, deviation_rate=rate,
                    threshold_value=settings.CALORIFIC_SEVERE_THRESHOLD,
                ))
            elif rate > settings.CALORIFIC_GENERAL_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.CALORIFIC_SHORTAGE,
                    severity=Severity.GENERAL,
                    description=(
                        f"热值亏损！港口 {pv:.0f} kcal/kg，入厂 {fv:.0f} kcal/kg，"
                        f"亏损率 {rate*100:.2f}%（阈值 {settings.CALORIFIC_GENERAL_THRESHOLD*100:.0f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation, deviation_rate=rate,
                    threshold_value=settings.CALORIFIC_GENERAL_THRESHOLD,
                ))

        # 合同热值违约检查（以入厂热值为准）
        cv = batch.contract_calorific_value
        if cv and fv:
            shortfall = cv - fv   # 正值 = 入厂低于合同
            if shortfall > settings.CONTRACT_CAL_SEVERE:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_CAL_BREACH,
                    severity=Severity.SEVERE,
                    description=(
                        f"入厂热值严重违约！入厂 {fv:.0f} kcal/kg，合同 {cv:.0f} kcal/kg，"
                        f"亏损 {shortfall:.0f} kcal/kg（阈值 {settings.CONTRACT_CAL_SEVERE:.0f}）"
                    ),
                    port_value=cv, factory_value=fv, deviation=shortfall,
                    deviation_rate=shortfall / cv if cv else None,
                    threshold_value=settings.CONTRACT_CAL_SEVERE,
                ))
            elif shortfall > settings.CONTRACT_CAL_GENERAL:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_CAL_BREACH,
                    severity=Severity.GENERAL,
                    description=(
                        f"入厂热值违约！入厂 {fv:.0f} kcal/kg，合同 {cv:.0f} kcal/kg，"
                        f"亏损 {shortfall:.0f} kcal/kg（阈值 {settings.CONTRACT_CAL_GENERAL:.0f}）"
                    ),
                    port_value=cv, factory_value=fv, deviation=shortfall,
                    deviation_rate=shortfall / cv if cv else None,
                    threshold_value=settings.CONTRACT_CAL_GENERAL,
                ))
        return results

    def _check_ash(
        self, port: QualityTest, factory: QualityTest, batch: CoalBatch
    ) -> List[AlertData]:
        """检查灰分偏差和合同违约"""
        results = []
        pv = port.ash_content
        fv = factory.ash_content
        if pv is not None and fv is not None:
            deviation = fv - pv   # 正值 = 入厂灰分高于港口（偏高）
            if deviation > settings.ASH_SEVERE_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.ASH_EXCESS,
                    severity=Severity.SEVERE,
                    description=(
                        f"灰分严重偏高！港口 {pv:.2f}%，入厂 {fv:.2f}%，"
                        f"偏差 +{deviation:.2f}%（阈值 {settings.ASH_SEVERE_THRESHOLD:.2f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.ASH_SEVERE_THRESHOLD,
                ))
            elif deviation > settings.ASH_GENERAL_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.ASH_EXCESS,
                    severity=Severity.GENERAL,
                    description=(
                        f"灰分偏高！港口 {pv:.2f}%，入厂 {fv:.2f}%，"
                        f"偏差 +{deviation:.2f}%（阈值 {settings.ASH_GENERAL_THRESHOLD:.2f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.ASH_GENERAL_THRESHOLD,
                ))

        # 合同灰分上限违约
        ca = batch.contract_ash_max
        if ca is not None and fv is not None:
            over = fv - ca   # 正值 = 入厂灰分超过合同上限
            if over > settings.CONTRACT_ASH_SEVERE:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_ASH_BREACH,
                    severity=Severity.SEVERE,
                    description=(
                        f"灰分严重超合同！入厂 {fv:.2f}%，合同上限 {ca:.2f}%，超出 {over:.2f}%"
                    ),
                    port_value=ca, factory_value=fv, deviation=over,
                    deviation_rate=over / ca if ca else None,
                    threshold_value=settings.CONTRACT_ASH_SEVERE,
                ))
            elif over > settings.CONTRACT_ASH_GENERAL:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_ASH_BREACH,
                    severity=Severity.GENERAL,
                    description=(
                        f"灰分超合同！入厂 {fv:.2f}%，合同上限 {ca:.2f}%，超出 {over:.2f}%"
                    ),
                    port_value=ca, factory_value=fv, deviation=over,
                    deviation_rate=over / ca if ca else None,
                    threshold_value=settings.CONTRACT_ASH_GENERAL,
                ))
        return results

    def _check_sulfur(
        self, port: QualityTest, factory: QualityTest, batch: CoalBatch
    ) -> List[AlertData]:
        """检查硫分偏差和合同违约"""
        results = []
        pv = port.sulfur_content
        fv = factory.sulfur_content
        if pv is not None and fv is not None:
            deviation = fv - pv   # 正值 = 入厂硫分高于港口
            if deviation > settings.SULFUR_SEVERE_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.SULFUR_EXCESS,
                    severity=Severity.SEVERE,
                    description=(
                        f"硫分严重偏高！港口 {pv:.3f}%，入厂 {fv:.3f}%，"
                        f"偏差 +{deviation:.3f}%（阈值 {settings.SULFUR_SEVERE_THRESHOLD:.3f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.SULFUR_SEVERE_THRESHOLD,
                ))
            elif deviation > settings.SULFUR_GENERAL_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.SULFUR_EXCESS,
                    severity=Severity.GENERAL,
                    description=(
                        f"硫分偏高！港口 {pv:.3f}%，入厂 {fv:.3f}%，"
                        f"偏差 +{deviation:.3f}%（阈值 {settings.SULFUR_GENERAL_THRESHOLD:.3f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.SULFUR_GENERAL_THRESHOLD,
                ))

        # 合同硫分上限违约
        cs = batch.contract_sulfur_max
        if cs is not None and fv is not None:
            over = fv - cs   # 正值 = 入厂硫分超过合同上限
            if over > settings.CONTRACT_SULFUR_SEVERE:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_SULFUR_BREACH,
                    severity=Severity.SEVERE,
                    description=(
                        f"硫分严重超合同！入厂 {fv:.3f}%，合同上限 {cs:.3f}%，超出 {over:.3f}%"
                    ),
                    port_value=cs, factory_value=fv, deviation=over,
                    deviation_rate=over / cs if cs else None,
                    threshold_value=settings.CONTRACT_SULFUR_SEVERE,
                ))
            elif over > settings.CONTRACT_SULFUR_GENERAL:
                results.append(AlertData(
                    alert_type=AlertType.CONTRACT_SULFUR_BREACH,
                    severity=Severity.GENERAL,
                    description=(
                        f"硫分超合同！入厂 {fv:.3f}%，合同上限 {cs:.3f}%，超出 {over:.3f}%"
                    ),
                    port_value=cs, factory_value=fv, deviation=over,
                    deviation_rate=over / cs if cs else None,
                    threshold_value=settings.CONTRACT_SULFUR_GENERAL,
                ))
        return results

    def _check_moisture(self, port: QualityTest, factory: QualityTest) -> List[AlertData]:
        """检查水分偏差"""
        results = []
        pv = port.moisture_total
        fv = factory.moisture_total
        if pv is not None and fv is not None:
            deviation = fv - pv   # 正值 = 入厂水分高于港口
            if deviation > settings.MOISTURE_SEVERE_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.MOISTURE_EXCESS,
                    severity=Severity.SEVERE,
                    description=(
                        f"水分严重偏高！港口 {pv:.2f}%，入厂 {fv:.2f}%，"
                        f"偏差 +{deviation:.2f}%（阈值 {settings.MOISTURE_SEVERE_THRESHOLD:.1f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.MOISTURE_SEVERE_THRESHOLD,
                ))
            elif deviation > settings.MOISTURE_GENERAL_THRESHOLD:
                results.append(AlertData(
                    alert_type=AlertType.MOISTURE_EXCESS,
                    severity=Severity.GENERAL,
                    description=(
                        f"水分偏高！港口 {pv:.2f}%，入厂 {fv:.2f}%，"
                        f"偏差 +{deviation:.2f}%（阈值 {settings.MOISTURE_GENERAL_THRESHOLD:.1f}%）"
                    ),
                    port_value=pv, factory_value=fv, deviation=deviation,
                    deviation_rate=deviation / pv if pv else None,
                    threshold_value=settings.MOISTURE_GENERAL_THRESHOLD,
                ))
        return results

    def _check_comprehensive(self, existing: List[AlertData]) -> List[AlertData]:
        """
        3个以上基础指标同时异常 → 触发综合预警（疑似以次充好）
        基础指标类型：热值亏损/灰分偏高/硫分偏高/水分偏高
        """
        base_types = {
            AlertType.CALORIFIC_SHORTAGE,
            AlertType.ASH_EXCESS,
            AlertType.SULFUR_EXCESS,
            AlertType.MOISTURE_EXCESS,
        }
        triggered = [d for d in existing if d.alert_type in base_types]
        if len(triggered) >= 3:
            severe_count = sum(1 for d in triggered if d.severity == Severity.SEVERE)
            return [AlertData(
                alert_type=AlertType.COMPREHENSIVE,
                severity=Severity.SEVERE if severe_count >= 2 else Severity.GENERAL,
                description=(
                    f"综合质量异常！共 {len(triggered)} 项指标偏差（热值/灰分/硫分/水分），疑似以次充好"
                ),
                port_value=None, factory_value=None, deviation=None, deviation_rate=None,
                threshold_value=3.0,
            )]
        return []

    def _compute_risk_score(self, alerts: Sequence[AlertData | QualityAlert]) -> float:
        """
        计算综合风险评分：
        score = Σ(预警类型权重 × 严重度系数)
        上限 5.0 分
        """
        if not alerts:
            return 0.0
        score = sum(
            self.TYPE_WEIGHTS.get(a.alert_type, 0.1) * self.SEVERITY_FACTORS.get(a.severity, 1.0)
            for a in alerts
        )
        return min(round(score, 2), 5.0)
