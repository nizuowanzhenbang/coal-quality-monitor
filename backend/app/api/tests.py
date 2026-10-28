"""化验记录接口"""
from datetime import datetime, timedelta, timezone
from math import isfinite
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.api.deps import get_db, get_current_user, require_operator
from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.user import User
from app.services.quality_engine import QualityEngine
from app.services.measurements import MeasurementInput, CONTROL_FIELDS, measurement_metadata
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/tests", tags=["化验记录"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────────

class TestCreateIn(MeasurementInput):
    batch_id: int
    test_type: TestType
    test_org: Optional[str] = None
    test_time: Optional[datetime] = None
    report_number: Optional[str] = None
    notes: Optional[str] = None


class TestUpdateIn(MeasurementInput):
    test_org: Optional[str] = None
    test_time: Optional[datetime] = None
    report_number: Optional[str] = None
    notes: Optional[str] = None


def _test_to_dict(t: QualityTest) -> dict:
    return {
        **measurement_metadata(),
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


def _try_auto_evaluate(batch: CoalBatch, db: Session) -> None:
    """新增化验后，若双端化验均存在则自动触发质量评估"""
    db.refresh(batch)
    # 重新加载 tests 关系
    batch_fresh = (
        db.query(CoalBatch)
        .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
        .filter(CoalBatch.id == batch.id)
        .first()
    )
    if not batch_fresh:
        return
    has_port = any(t.test_type == TestType.PORT for t in batch_fresh.tests)
    has_factory = any(t.test_type == TestType.FACTORY for t in batch_fresh.tests)
    if has_port and has_factory:
        engine = QualityEngine()
        engine.evaluate(batch_fresh, db)


# ── 路由 ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict, summary="化验记录列表")
def list_tests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    batch_id: Optional[int] = Query(None),
    test_type: Optional[TestType] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(QualityTest)
    if batch_id is not None:
        query = query.filter(QualityTest.batch_id == batch_id)
    if test_type is not None:
        query = query.filter(QualityTest.test_type == test_type)

    total = query.count()
    tests = query.order_by(QualityTest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return paginate_response([_test_to_dict(t) for t in tests], total, page, page_size)


@router.post("", response_model=dict, summary="新增化验记录")
def create_test(
    body: TestCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    batch = db.query(CoalBatch).filter(CoalBatch.id == body.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    # 同类型化验已存在则拒绝重复录入
    existing = (
        db.query(QualityTest)
        .filter(QualityTest.batch_id == body.batch_id, QualityTest.test_type == body.test_type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"该批次已存在 {body.test_type} 化验记录，如需修改请使用 PUT /api/tests/{existing.id}",
        )

    test = QualityTest(**body.model_dump(exclude=CONTROL_FIELDS))
    db.add(test)

    # 更新批次状态
    if batch.status == BatchStatus.PENDING:
        batch.status = BatchStatus.PARTIAL
    batch.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(test)

    # 若双端化验齐全则自动评估
    _try_auto_evaluate(batch, db)

    return api_response(data=_test_to_dict(test), message="化验记录创建成功")


@router.get("/{test_id}", response_model=dict, summary="化验记录详情")
def get_test(
    test_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    test = db.query(QualityTest).filter(QualityTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="化验记录不存在")
    return api_response(data=_test_to_dict(test))


@router.put("/{test_id}", response_model=dict, summary="更新化验数据")
def update_test(
    test_id: int,
    body: TestUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    test = db.query(QualityTest).filter(QualityTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="化验记录不存在")

    for field, value in body.model_dump(exclude_unset=True, exclude=CONTROL_FIELDS).items():
        setattr(test, field, value)
    db.commit()
    db.refresh(test)

    # 更新后重新评估质量
    batch = (
        db.query(CoalBatch)
        .options(joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts))
        .filter(CoalBatch.id == test.batch_id)
        .first()
    )
    if batch:
        _try_auto_evaluate(batch, db)

    return api_response(data=_test_to_dict(test), message="更新成功")


class EnergyMeasurementDeclaration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    offset_minutes: StrictInt = Field(ge=-840, le=840)
    time_evidence: str = Field(min_length=1, max_length=500)

    @field_validator('time_evidence')
    @classmethod
    def evidence_not_blank(cls, value):
        if not value.strip():
            raise ValueError('请提供时区来源依据')
        return value


@router.post('/{test_id}/energy-measurement', response_model=dict, summary='导出能效情景所需的煤质化验数据')
def export_energy_measurement(
    test_id: int, body: EnergyMeasurementDeclaration,
    db: Session = Depends(get_db), _: User = Depends(require_operator),
):
    instance = settings.QUALITY_SOURCE_INSTANCE
    if not re.fullmatch(r'\S(?:.*\S)?', instance) or len(instance) > 128:
        raise HTTPException(status_code=503, detail='未配置有效的煤质来源实例标识')
    test = db.query(QualityTest).filter(QualityTest.id == test_id).first()
    if test is None:
        raise HTTPException(status_code=404, detail='化验记录不存在')
    value = test.calorific_value_net
    if test.test_type != TestType.FACTORY or value is None or not isfinite(value) or not 0 < value <= 10000:
        raise HTTPException(status_code=422, detail='需要范围内的入厂收到基低位热值')
    if test.test_time is None or test.test_time.tzinfo is not None:
        raise HTTPException(status_code=422, detail='化验时间缺失或存储时区形式不支持声明')
    measured = test.test_time.replace(tzinfo=timezone(timedelta(minutes=body.offset_minutes)))
    try:
        measured.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise HTTPException(status_code=422, detail='声明的时间转换UTC超出范围') from exc
    return api_response(data={
        'measurement': {
            'source_system': 'coal-quality-monitor', 'source_instance': instance,
            'batch_id': str(test.batch_id), 'test_id': str(test.id),
            'metric': 'Qnet', 'basis': 'ar', 'unit': 'kcal/kg',
            'value': value, 'measured_at': measured.isoformat(),
        },
        'time_provenance': {
            'kind': 'caller_declared_offset', 'offset_minutes': body.offset_minutes,
            'evidence': body.time_evidence, 'stored_time': test.test_time.isoformat(),
        },
    })
