"""批次管理接口"""
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_operator
from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.alert import QualityAlert
from app.models.supplier import Supplier
from app.models.user import User
from app.services.quality_engine import QualityEngine
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/batches", tags=["批次管理"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────────

class BatchCreateIn(BaseModel):
    batch_number: str
    supplier_id: int
    coal_type: Optional[str] = None
    departure_port: Optional[str] = None
    arrival_plant: Optional[str] = None
    contract_quantity: Optional[float] = None
    actual_quantity: Optional[float] = None
    contract_calorific_value: Optional[float] = None
    contract_ash_max: Optional[float] = None
    contract_sulfur_max: Optional[float] = None
    contract_moisture_max: Optional[float] = None
    arrival_date: Optional[datetime] = None
    notes: Optional[str] = None


class BatchUpdateIn(BaseModel):
    coal_type: Optional[str] = None
    departure_port: Optional[str] = None
    arrival_plant: Optional[str] = None
    contract_quantity: Optional[float] = None
    actual_quantity: Optional[float] = None
    contract_calorific_value: Optional[float] = None
    contract_ash_max: Optional[float] = None
    contract_sulfur_max: Optional[float] = None
    contract_moisture_max: Optional[float] = None
    arrival_date: Optional[datetime] = None
    notes: Optional[str] = None


def _batch_to_dict(batch: CoalBatch, supplier_name: str = "") -> dict:
    """批次序列化（列表用，不含化验/预警详情）"""
    return {
        "id": batch.id,
        "batch_number": batch.batch_number,
        "supplier_id": batch.supplier_id,
        "supplier_name": supplier_name,
        "coal_type": batch.coal_type,
        "departure_port": batch.departure_port,
        "arrival_plant": batch.arrival_plant,
        "contract_quantity": batch.contract_quantity,
        "actual_quantity": batch.actual_quantity,
        "contract_calorific_value": batch.contract_calorific_value,
        "contract_ash_max": batch.contract_ash_max,
        "contract_sulfur_max": batch.contract_sulfur_max,
        "contract_moisture_max": batch.contract_moisture_max,
        "status": batch.status,
        "alert_count": batch.alert_count,
        "risk_score": batch.risk_score,
        "arrival_date": batch.arrival_date.isoformat() if batch.arrival_date else None,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "notes": batch.notes,
    }


def _test_to_dict(t: QualityTest) -> dict:
    return {
        "id": t.id,
        "batch_id": t.batch_id,
        "test_type": t.test_type,
        "test_org": t.test_org,
        "test_time": t.test_time.isoformat() if t.test_time else None,
        "report_number": t.report_number,
        "calorific_value_net": t.calorific_value_net,
        "calorific_value_gross": t.calorific_value_gross,
        "ash_content": t.ash_content,
        "sulfur_content": t.sulfur_content,
        "moisture_total": t.moisture_total,
        "moisture_inherent": t.moisture_inherent,
        "volatile_matter": t.volatile_matter,
        "fixed_carbon": t.fixed_carbon,
        "notes": t.notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _alert_to_dict(a: QualityAlert) -> dict:
    return {
        "id": a.id,
        "batch_id": a.batch_id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "description": a.description,
        "port_value": a.port_value,
        "factory_value": a.factory_value,
        "deviation": a.deviation,
        "deviation_rate": a.deviation_rate,
        "threshold_value": a.threshold_value,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _build_comparison(port: Optional[QualityTest], factory: Optional[QualityTest]) -> Optional[dict]:
    """构建两份化验的对比结果"""
    if not port or not factory:
        return None

    def diff(pv, fv):
        if pv is None or fv is None:
            return None
        return round(fv - pv, 4)

    def rate(pv, fv):
        if pv is None or fv is None or pv == 0:
            return None
        return round((fv - pv) / pv, 6)

    return {
        "calorific_value_net": {
            "port": port.calorific_value_net,
            "factory": factory.calorific_value_net,
            "deviation": diff(port.calorific_value_net, factory.calorific_value_net),
            "deviation_rate": rate(port.calorific_value_net, factory.calorific_value_net),
        },
        "ash_content": {
            "port": port.ash_content,
            "factory": factory.ash_content,
            "deviation": diff(port.ash_content, factory.ash_content),
            "deviation_rate": rate(port.ash_content, factory.ash_content),
        },
        "sulfur_content": {
            "port": port.sulfur_content,
            "factory": factory.sulfur_content,
            "deviation": diff(port.sulfur_content, factory.sulfur_content),
            "deviation_rate": rate(port.sulfur_content, factory.sulfur_content),
        },
        "moisture_total": {
            "port": port.moisture_total,
            "factory": factory.moisture_total,
            "deviation": diff(port.moisture_total, factory.moisture_total),
            "deviation_rate": rate(port.moisture_total, factory.moisture_total),
        },
        "volatile_matter": {
            "port": port.volatile_matter,
            "factory": factory.volatile_matter,
            "deviation": diff(port.volatile_matter, factory.volatile_matter),
            "deviation_rate": rate(port.volatile_matter, factory.volatile_matter),
        },
    }


# ── 路由 ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict, summary="批次列表（分页）")
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    supplier_id: Optional[int] = Query(None),
    status: Optional[BatchStatus] = Query(None),
    batch_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(CoalBatch).options(joinedload(CoalBatch.supplier))

    if supplier_id is not None:
        query = query.filter(CoalBatch.supplier_id == supplier_id)
    if status is not None:
        query = query.filter(CoalBatch.status == status)
    if batch_number:
        query = query.filter(CoalBatch.batch_number.contains(batch_number))

    total = query.count()
    batches = query.order_by(CoalBatch.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [_batch_to_dict(b, b.supplier.name if b.supplier else "") for b in batches]
    return paginate_response(items, total, page, page_size)


@router.post("", response_model=dict, summary="创建批次")
def create_batch(
    body: BatchCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if db.query(CoalBatch).filter(CoalBatch.batch_number == body.batch_number).first():
        raise HTTPException(status_code=400, detail="批次号已存在")
    supplier = db.query(Supplier).filter(Supplier.id == body.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    batch = CoalBatch(**body.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return api_response(data=_batch_to_dict(batch, supplier.name), message="批次创建成功")


@router.get("/{batch_id}", response_model=dict, summary="批次详情（含化验记录和预警）")
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = (
        db.query(CoalBatch)
        .options(
            joinedload(CoalBatch.supplier),
            joinedload(CoalBatch.tests),
            joinedload(CoalBatch.alerts),
        )
        .filter(CoalBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    port_test = next((t for t in batch.tests if t.test_type == TestType.PORT), None)
    factory_test = next((t for t in batch.tests if t.test_type == TestType.FACTORY), None)

    data = _batch_to_dict(batch, batch.supplier.name if batch.supplier else "")
    data["port_test"] = _test_to_dict(port_test) if port_test else None
    data["factory_test"] = _test_to_dict(factory_test) if factory_test else None
    data["comparison"] = _build_comparison(port_test, factory_test)
    data["alerts"] = [_alert_to_dict(a) for a in batch.alerts]
    return api_response(data=data)


@router.put("/{batch_id}", response_model=dict, summary="更新批次信息")
def update_batch(
    batch_id: int,
    body: BatchUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    batch = db.query(CoalBatch).filter(CoalBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(batch, field, value)
    batch.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(batch)
    return api_response(data=_batch_to_dict(batch), message="更新成功")


@router.post("/{batch_id}/evaluate", response_model=dict, summary="触发质量评估引擎")
def evaluate_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    batch = (
        db.query(CoalBatch)
        .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
        .filter(CoalBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    port_test = next((t for t in batch.tests if t.test_type == TestType.PORT), None)
    factory_test = next((t for t in batch.tests if t.test_type == TestType.FACTORY), None)
    if not port_test or not factory_test:
        raise HTTPException(status_code=400, detail="需要港口和入厂两份化验记录才能评估")

    engine = QualityEngine()
    alerts = engine.evaluate(batch, db)

    return api_response(
        data={
            "batch_id": batch_id,
            "status": batch.status,
            "alert_count": batch.alert_count,
            "risk_score": batch.risk_score,
            "alerts": [_alert_to_dict(a) for a in alerts],
        },
        message=f"评估完成，生成 {len(alerts)} 条预警",
    )
