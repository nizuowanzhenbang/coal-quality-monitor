"""供应商质量评分器"""
from typing import List
from sqlalchemy.orm import Session
from app.models.batch import CoalBatch, BatchStatus
from app.models.supplier import Supplier
from app.models.alert import QualityAlert, Severity, AlertType
from app.config import settings

TRANSPORT_ALERT_TYPES = {
    AlertType.TRANSPORT_WEIGHT,
    AlertType.TRANSPORT_TIME,
    AlertType.TRANSPORT_SEAL,
}


class SupplierScorer:
    """
    基于最近 N 个批次的质量+运输表现给供应商打分（0-100）。

    评分规则（质量维度）：
    - 无预警批次：不扣分
    - 仅一般预警：每批 -3 分
    - 含严重预警：每批 -10 分
    - 含综合异常：每批 -15 分

    评分规则（运输维度，叠加扣分）：
    - 含运输一般预警：额外 -2 分
    - 含运输严重预警：额外 -5 分
    """

    def recalculate(self, supplier: Supplier, db: Session) -> float:
        """重新计算供应商信用评分并持久化"""
        recent_batches = (
            db.query(CoalBatch)
            .filter(
                CoalBatch.supplier_id == supplier.id,
                CoalBatch.status.in_([BatchStatus.COMPLETED, BatchStatus.ALERT, BatchStatus.SEVERE]),
            )
            .order_by(CoalBatch.created_at.desc())
            .limit(settings.SUPPLIER_SCORE_WINDOW)
            .all()
        )

        if not recent_batches:
            return supplier.credit_score

        score = 100.0
        for batch in recent_batches:
            alerts = db.query(QualityAlert).filter(QualityAlert.batch_id == batch.id).all()
            if not alerts:
                continue

            quality_alerts = [a for a in alerts if a.alert_type not in TRANSPORT_ALERT_TYPES]
            transport_alerts = [a for a in alerts if a.alert_type in TRANSPORT_ALERT_TYPES]

            # 质量维度扣分
            if quality_alerts:
                has_comprehensive = any(
                    a.alert_type == AlertType.COMPREHENSIVE for a in quality_alerts
                )
                has_severe = any(a.severity == Severity.SEVERE for a in quality_alerts)
                if has_comprehensive:
                    score -= 15
                elif has_severe:
                    score -= 10
                else:
                    score -= 3

            # 运输维度叠加扣分
            if transport_alerts:
                has_transport_severe = any(
                    a.severity == Severity.SEVERE for a in transport_alerts
                )
                if has_transport_severe:
                    score -= 5
                else:
                    score -= 2

        score = max(0.0, min(100.0, score))
        supplier.credit_score = round(score, 1)
        db.commit()
        return supplier.credit_score
