"""化验记录接口"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_operator
from app.models.batch import CoalBatch, BatchStatus
from app.models.test import QualityTest, TestType
from app.models.user import User
from app.services.quality_engine import QualityEngine
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/tests", tags=["化验记录"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────────

class TestCreateIn(BaseModel):
    batch_id: int
    test_type: TestType
    test_org: Optional[str] = None
    test_time: Optional[datetime] = None
    report_number: Optional[str] = None
    calorific_value_net: Optional[float] = None
    calorific_value_gross: Optional[float] = None
    ash_content: Optional[float] = None
    sulfur_content: Optional[float] = None
    moisture_total: Optional[float] = None
    moisture_inherent: Optional[float] = None
    volatile_matter: Optional[float] = None
    fixed_carbon: Optional[float] = None
    notes: Optional[str] = None


class TestUpdateIn(BaseModel):
    test_org: Optional[str] = None
    test_time: Optional[datetime] = None
    report_number: Optional[str] = None
    calorific_value_net: Optional[float] = None
    calorific_value_gross: Optional[float] = None
    ash_content: Optional[float] = None
    sulfur_content: Optional[float] = None
    moisture_total: Optional[float] = None
    moisture_inherent: Optional[float] = None
    volatile_matter: Optional[float] = None
    fixed_carbon: Optional[float] = None
    notes: Optional[str] = None


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

    test = QualityTest(**body.model_dump())
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

    for field, value in body.model_dump(exclude_unset=True).items():
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
