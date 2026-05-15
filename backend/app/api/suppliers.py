"""供应商管理接口"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_operator, require_admin
from app.models.batch import CoalBatch, BatchStatus
from app.models.alert import QualityAlert, Severity
from app.models.supplier import Supplier, SupplierStatus
from app.models.user import User
from app.services.supplier_scorer import SupplierScorer
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/suppliers", tags=["供应商管理"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────────

class SupplierCreateIn(BaseModel):
    name: str
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    coal_types: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdateIn(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    coal_types: Optional[str] = None
    status: Optional[SupplierStatus] = None
    notes: Optional[str] = None


def _supplier_to_dict(supplier: Supplier, extra: Optional[dict] = None) -> dict:
    d = {
        "id": supplier.id,
        "name": supplier.name,
        "contact_person": supplier.contact_person,
        "contact_phone": supplier.contact_phone,
        "coal_types": supplier.coal_types,
        "credit_score": supplier.credit_score,
        "status": supplier.status,
        "notes": supplier.notes,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
        "updated_at": supplier.updated_at.isoformat() if supplier.updated_at else None,
    }
    if extra:
        d.update(extra)
    return d


def _get_supplier_alert_stats(supplier_id: int, db: Session) -> dict:
    """获取供应商的预警统计（总预警数/严重预警数/异常批次率）"""
    batch_ids = [
        row[0] for row in
        db.query(CoalBatch.id).filter(CoalBatch.supplier_id == supplier_id).all()
    ]
    if not batch_ids:
        return {"total_alerts": 0, "severe_alerts": 0, "total_batches": 0, "anomaly_rate": 0.0}

    total_batches = len(batch_ids)
    total_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(QualityAlert.batch_id.in_(batch_ids))
        .scalar() or 0
    )
    severe_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(QualityAlert.batch_id.in_(batch_ids), QualityAlert.severity == Severity.SEVERE)
        .scalar() or 0
    )
    anomaly_batches = (
        db.query(func.count(CoalBatch.id))
        .filter(
            CoalBatch.supplier_id == supplier_id,
            CoalBatch.status.in_([BatchStatus.ALERT, BatchStatus.SEVERE]),
        )
        .scalar() or 0
    )
    return {
        "total_alerts": total_alerts,
        "severe_alerts": severe_alerts,
        "total_batches": total_batches,
        "anomaly_rate": round(anomaly_batches / total_batches, 4) if total_batches else 0.0,
    }


# ── 路由 ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict, summary="供应商列表（附预警统计）")
def list_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[SupplierStatus] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Supplier)
    if status is not None:
        query = query.filter(Supplier.status == status)

    total = query.count()
    suppliers = query.order_by(Supplier.credit_score.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for s in suppliers:
        stats = _get_supplier_alert_stats(s.id, db)
        items.append(_supplier_to_dict(s, stats))

    return paginate_response(items, total, page, page_size)


@router.post("", response_model=dict, summary="创建供应商")
def create_supplier(
    body: SupplierCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if db.query(Supplier).filter(Supplier.name == body.name).first():
        raise HTTPException(status_code=400, detail="供应商名称已存在")

    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return api_response(data=_supplier_to_dict(supplier), message="供应商创建成功")


@router.get("/{supplier_id}", response_model=dict, summary="供应商详情（含最近批次和质量趋势）")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    stats = _get_supplier_alert_stats(supplier_id, db)

    # 最近20个批次（含化验和预警数量）
    recent_batches = (
        db.query(CoalBatch)
        .filter(CoalBatch.supplier_id == supplier_id)
        .order_by(CoalBatch.created_at.desc())
        .limit(20)
        .all()
    )
    batch_list = []
    for b in recent_batches:
        batch_list.append({
            "id": b.id,
            "batch_number": b.batch_number,
            "coal_type": b.coal_type,
            "status": b.status,
            "alert_count": b.alert_count,
            "risk_score": b.risk_score,
            "arrival_date": b.arrival_date.isoformat() if b.arrival_date else None,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })

    # 质量趋势：最近20批次的热值/灰分/硫分平均对比偏差
    from app.models.test import QualityTest, TestType
    trend = []
    for b in recent_batches:
        port_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == b.id, QualityTest.test_type == TestType.PORT)
            .first()
        )
        factory_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == b.id, QualityTest.test_type == TestType.FACTORY)
            .first()
        )
        if port_t and factory_t:
            cal_dev = None
            if port_t.calorific_value_net and factory_t.calorific_value_net and port_t.calorific_value_net > 0:
                cal_dev = round(
                    (port_t.calorific_value_net - factory_t.calorific_value_net) / port_t.calorific_value_net * 100,
                    3,
                )
            ash_dev = None
            if port_t.ash_content is not None and factory_t.ash_content is not None:
                ash_dev = round(factory_t.ash_content - port_t.ash_content, 3)
            sulfur_dev = None
            if port_t.sulfur_content is not None and factory_t.sulfur_content is not None:
                sulfur_dev = round(factory_t.sulfur_content - port_t.sulfur_content, 4)

            trend.append({
                "batch_id": b.id,
                "batch_number": b.batch_number,
                "date": b.created_at.strftime("%Y-%m-%d") if b.created_at else None,
                "calorific_deviation_pct": cal_dev,
                "ash_deviation": ash_dev,
                "sulfur_deviation": sulfur_dev,
                "risk_score": b.risk_score,
            })

    data = _supplier_to_dict(supplier, stats)
    data["recent_batches"] = batch_list
    data["quality_trend"] = trend

    return api_response(data=data)


@router.put("/{supplier_id}", response_model=dict, summary="更新供应商信息")
def update_supplier(
    supplier_id: int,
    body: SupplierUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != supplier.name:
        if db.query(Supplier).filter(Supplier.name == updates["name"]).first():
            raise HTTPException(status_code=400, detail="供应商名称已被占用")

    for field, value in updates.items():
        setattr(supplier, field, value)
    supplier.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(supplier)
    return api_response(data=_supplier_to_dict(supplier), message="更新成功")


@router.post("/{supplier_id}/recalculate-score", response_model=dict, summary="手动重算信用分")
def recalculate_score(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    scorer = SupplierScorer()
    new_score = scorer.recalculate(supplier, db)
    return api_response(
        data={"supplier_id": supplier_id, "credit_score": new_score},
        message=f"信用分已重新计算：{new_score}",
    )
