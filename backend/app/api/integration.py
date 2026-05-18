"""闭环集成接口：接收运输监督系统的运输完成事件"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.batch import CoalBatch, BatchStatus
from app.models.alert import QualityAlert, AlertType, Severity, AlertStatus
from app.models.supplier import Supplier
from app.services.supplier_scorer import SupplierScorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integration", tags=["闭环集成"])

TRANSPORT_ALERT_MAP = {
    "WEIGHT_SHORTAGE": AlertType.TRANSPORT_WEIGHT,
    "WEIGHT_OVERAGE": AlertType.TRANSPORT_WEIGHT,
    "TIME_EXCESSIVE": AlertType.TRANSPORT_TIME,
    "SEAL_MISMATCH": AlertType.TRANSPORT_SEAL,
    "SEAL_DAMAGED": AlertType.TRANSPORT_SEAL,
}


class TransportAlertItem(BaseModel):
    alert_type: str
    severity: str
    description: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None


class TransportEventPayload(BaseModel):
    batch_number: str
    plate_number: Optional[str] = None
    supplier_name: Optional[str] = None
    transport_id: Optional[int] = None
    status: str = "NORMAL"
    weight_diff_ratio: Optional[float] = None
    transport_duration: Optional[int] = None
    departure_port: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_net_weight: Optional[float] = None
    arrival_net_weight: Optional[float] = None
    alerts: List[TransportAlertItem] = []


@router.post("/transport-event", summary="接收运输完成事件")
def receive_transport_event(
    payload: TransportEventPayload,
    x_integration_secret: str = Header(..., alias="X-Integration-Secret"),
):
    """
    接收来自 coal-transport-monitor 的运输完成事件。

    流程：
    1. 验证集成密钥
    2. 根据 batch_number 匹配批次
    3. 将运输预警转为质量系统预警
    4. 更新批次状态
    5. 重新计算供应商信用评分
    """
    if x_integration_secret != settings.INTEGRATION_SECRET:
        raise HTTPException(status_code=403, detail="集成密钥无效")

    db = SessionLocal()
    try:
        batch = (
            db.query(CoalBatch)
            .filter(CoalBatch.batch_number == payload.batch_number)
            .first()
        )
        if not batch:
            return {
                "code": 404,
                "message": f"未找到批次 {payload.batch_number}",
                "matched": False,
            }

        db.query(QualityAlert).filter(
            QualityAlert.batch_id == batch.id,
            QualityAlert.alert_type.in_([
                AlertType.TRANSPORT_WEIGHT,
                AlertType.TRANSPORT_TIME,
                AlertType.TRANSPORT_SEAL,
            ]),
        ).delete(synchronize_session="fetch")

        created_alerts: list[QualityAlert] = []
        for ta in payload.alerts:
            mapped_type = TRANSPORT_ALERT_MAP.get(ta.alert_type)
            if not mapped_type:
                continue
            severity = Severity.SEVERE if ta.severity == "SEVERE" else Severity.GENERAL
            prefix = f"[运输监督] "
            alert = QualityAlert(
                batch_id=batch.id,
                alert_type=mapped_type,
                severity=severity,
                description=prefix + ta.description,
                port_value=payload.departure_net_weight,
                factory_value=payload.arrival_net_weight,
                deviation=ta.actual_value,
                deviation_rate=payload.weight_diff_ratio,
                threshold_value=ta.threshold_value,
                status=AlertStatus.PENDING,
            )
            db.add(alert)
            created_alerts.append(alert)

        if created_alerts:
            has_severe = any(a.severity == Severity.SEVERE for a in created_alerts)
            existing_quality_alerts = (
                db.query(QualityAlert)
                .filter(
                    QualityAlert.batch_id == batch.id,
                    QualityAlert.alert_type.notin_([
                        AlertType.TRANSPORT_WEIGHT,
                        AlertType.TRANSPORT_TIME,
                        AlertType.TRANSPORT_SEAL,
                    ]),
                )
                .all()
            )
            all_severe = has_severe or any(
                a.severity == Severity.SEVERE for a in existing_quality_alerts
            )
            if all_severe:
                batch.status = BatchStatus.SEVERE
            elif batch.status not in (BatchStatus.SEVERE,):
                batch.status = BatchStatus.ALERT

            batch.alert_count = len(existing_quality_alerts) + len(created_alerts)

        db.commit()

        if batch.supplier_id:
            supplier = db.query(Supplier).filter(Supplier.id == batch.supplier_id).first()
            if supplier:
                scorer = SupplierScorer()
                scorer.recalculate(supplier, db)

        for a in created_alerts:
            db.refresh(a)

        if created_alerts:
            _broadcast_transport_alerts(batch, created_alerts)

        return {
            "code": 200,
            "message": f"已接收 {len(created_alerts)} 条运输预警",
            "matched": True,
            "batch_id": batch.id,
            "alerts_created": len(created_alerts),
        }
    finally:
        db.close()


def _broadcast_transport_alerts(batch: CoalBatch, alerts: list[QualityAlert]) -> None:
    """将运输预警广播到 WebSocket 客户端"""
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
                    "alert_type": alert.alert_type.value if hasattr(alert.alert_type, 'value') else alert.alert_type,
                    "severity": alert.severity.value if hasattr(alert.severity, 'value') else alert.severity,
                    "description": alert.description,
                    "source": "transport",
                    "created_at": alert.created_at.isoformat() if alert.created_at else None,
                },
            }
            if loop.is_running():
                asyncio.ensure_future(broadcast(payload))
    except Exception:
        pass
