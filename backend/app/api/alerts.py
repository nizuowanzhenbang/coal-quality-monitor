"""预警管理接口"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_operator
from app.models.alert import QualityAlert, AlertType, Severity, AlertStatus
from app.models.batch import CoalBatch
from app.models.supplier import Supplier
from app.models.user import User
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/alerts", tags=["预警管理"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────────

class ResolveIn(BaseModel):
    resolution_notes: Optional[str] = None


def _alert_to_dict(alert: QualityAlert, batch: Optional[CoalBatch] = None) -> dict:
    supplier_name = ""
    batch_number = ""
    if batch:
        batch_number = batch.batch_number
        if batch.supplier:
            supplier_name = batch.supplier.name
    return {
        "id": alert.id,
        "batch_id": alert.batch_id,
        "batch_number": batch_number,
        "supplier_name": supplier_name,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "description": alert.description,
        "port_value": alert.port_value,
        "factory_value": alert.factory_value,
        "deviation": alert.deviation,
        "deviation_rate": alert.deviation_rate,
        "threshold_value": alert.threshold_value,
        "status": alert.status,
        "resolved_by": alert.resolved_by,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolution_notes": alert.resolution_notes,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


# ── 路由 ───────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=dict, summary="预警统计")
def alert_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按类型/严重度/状态统计预警数量"""
    # 按类型统计
    by_type = (
        db.query(QualityAlert.alert_type, func.count(QualityAlert.id).label("count"))
        .group_by(QualityAlert.alert_type)
        .all()
    )
    # 按严重度统计
    by_severity = (
        db.query(QualityAlert.severity, func.count(QualityAlert.id).label("count"))
        .group_by(QualityAlert.severity)
        .all()
    )
    # 按处理状态统计
    by_status = (
        db.query(QualityAlert.status, func.count(QualityAlert.id).label("count"))
        .group_by(QualityAlert.status)
        .all()
    )

    return api_response(data={
        "by_type": {row.alert_type: row.count for row in by_type},
        "by_severity": {row.severity: row.count for row in by_severity},
        "by_status": {row.status: row.count for row in by_status},
        "total": sum(row.count for row in by_status),
    })


@router.get("", response_model=dict, summary="预警列表（分页）")
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    severity: Optional[Severity] = Query(None),
    status: Optional[AlertStatus] = Query(None),
    alert_type: Optional[AlertType] = Query(None),
    supplier_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = (
        db.query(QualityAlert)
        .join(CoalBatch, QualityAlert.batch_id == CoalBatch.id)
        .options(
            joinedload(QualityAlert.batch).joinedload(CoalBatch.supplier)
        )
    )
    if severity is not None:
        query = query.filter(QualityAlert.severity == severity)
    if status is not None:
        query = query.filter(QualityAlert.status == status)
    if alert_type is not None:
        query = query.filter(QualityAlert.alert_type == alert_type)
    if supplier_id is not None:
        query = query.filter(CoalBatch.supplier_id == supplier_id)

    total = query.count()
    alerts = (
        query.order_by(QualityAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_alert_to_dict(a, a.batch) for a in alerts]
    return paginate_response(items, total, page, page_size)


@router.put("/{alert_id}/acknowledge", response_model=dict, summary="确认预警")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    alert = db.query(QualityAlert).filter(QualityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    if alert.status != AlertStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"预警当前状态为 {alert.status}，无法确认")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.resolved_by = current_user.username
    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(alert)
    return api_response(data=_alert_to_dict(alert), message="已确认预警")


@router.put("/{alert_id}/resolve", response_model=dict, summary="解决预警")
def resolve_alert(
    alert_id: int,
    body: ResolveIn = ResolveIn(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    alert = db.query(QualityAlert).filter(QualityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="预警已解决")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = current_user.username
    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.resolution_notes = body.resolution_notes
    db.commit()
    db.refresh(alert)
    return api_response(data=_alert_to_dict(alert), message="预警已解决")


@router.put("/{alert_id}/dismiss", response_model=dict, summary="忽略预警")
def dismiss_alert(
    alert_id: int,
    body: ResolveIn = ResolveIn(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    alert = db.query(QualityAlert).filter(QualityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    if alert.status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
        raise HTTPException(status_code=400, detail=f"预警当前状态为 {alert.status}，无法忽略")

    alert.status = AlertStatus.DISMISSED
    alert.resolved_by = current_user.username
    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.resolution_notes = body.resolution_notes
    db.commit()
    db.refresh(alert)
    return api_response(data=_alert_to_dict(alert), message="预警已忽略")
