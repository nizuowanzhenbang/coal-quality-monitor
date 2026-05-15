"""数据导出接口（CSV）"""
import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user
from app.models.batch import CoalBatch, BatchStatus
from app.models.alert import QualityAlert
from app.models.supplier import Supplier
from app.models.test import QualityTest, TestType
from app.models.user import User

router = APIRouter(prefix="/api/export", tags=["数据导出"])


def _make_csv_response(rows: list[list], headers: list[str], filename: str) -> StreamingResponse:
    """将数据转换为 CSV 流式响应"""
    output = io.StringIO()
    # 写入 UTF-8 BOM，使 Excel 正确识别中文
    output.write("﻿")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8-sig",
        },
    )


@router.get("/batches", summary="导出批次和对比结果（CSV）")
def export_batches(
    supplier_id: Optional[int] = Query(None),
    status: Optional[BatchStatus] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """导出批次列表及港口/入厂化验对比结果"""
    query = (
        db.query(CoalBatch)
        .options(joinedload(CoalBatch.supplier), joinedload(CoalBatch.tests))
    )
    if supplier_id is not None:
        query = query.filter(CoalBatch.supplier_id == supplier_id)
    if status is not None:
        query = query.filter(CoalBatch.status == status)

    batches = query.order_by(CoalBatch.created_at.desc()).all()

    headers = [
        "批次号", "供应商", "煤种", "发货港口", "到厂名称",
        "合同数量(吨)", "实际数量(吨)", "批次状态", "预警数量", "风险评分",
        "合同热值", "合同灰分上限", "合同硫分上限", "合同水分上限",
        "港口热值(kcal/kg)", "入厂热值(kcal/kg)", "热值偏差", "热值偏差率(%)",
        "港口灰分(%)", "入厂灰分(%)", "灰分偏差",
        "港口硫分(%)", "入厂硫分(%)", "硫分偏差",
        "港口水分(%)", "入厂水分(%)", "水分偏差",
        "到厂日期", "创建时间",
    ]

    rows = []
    for b in batches:
        port_t = next((t for t in b.tests if t.test_type == TestType.PORT), None)
        factory_t = next((t for t in b.tests if t.test_type == TestType.FACTORY), None)

        def _d(pv, fv):
            if pv is not None and fv is not None:
                return round(fv - pv, 4)
            return ""

        def _r(pv, fv):
            if pv and fv and pv != 0:
                return round((fv - pv) / pv * 100, 3)
            return ""

        rows.append([
            b.batch_number,
            b.supplier.name if b.supplier else "",
            b.coal_type or "",
            b.departure_port or "",
            b.arrival_plant or "",
            b.contract_quantity or "",
            b.actual_quantity or "",
            b.status,
            b.alert_count,
            b.risk_score,
            b.contract_calorific_value or "",
            b.contract_ash_max or "",
            b.contract_sulfur_max or "",
            b.contract_moisture_max or "",
            port_t.calorific_value_net if port_t else "",
            factory_t.calorific_value_net if factory_t else "",
            _d(port_t.calorific_value_net if port_t else None, factory_t.calorific_value_net if factory_t else None),
            _r(port_t.calorific_value_net if port_t else None, factory_t.calorific_value_net if factory_t else None),
            port_t.ash_content if port_t else "",
            factory_t.ash_content if factory_t else "",
            _d(port_t.ash_content if port_t else None, factory_t.ash_content if factory_t else None),
            port_t.sulfur_content if port_t else "",
            factory_t.sulfur_content if factory_t else "",
            _d(port_t.sulfur_content if port_t else None, factory_t.sulfur_content if factory_t else None),
            port_t.moisture_total if port_t else "",
            factory_t.moisture_total if factory_t else "",
            _d(port_t.moisture_total if port_t else None, factory_t.moisture_total if factory_t else None),
            b.arrival_date.strftime("%Y-%m-%d") if b.arrival_date else "",
            b.created_at.strftime("%Y-%m-%d %H:%M:%S") if b.created_at else "",
        ])

    filename = f"batches_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    return _make_csv_response(rows, headers, filename)


@router.get("/alerts", summary="导出预警记录（CSV）")
def export_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """导出预警列表"""
    query = (
        db.query(QualityAlert)
        .join(CoalBatch, QualityAlert.batch_id == CoalBatch.id)
        .options(joinedload(QualityAlert.batch).joinedload(CoalBatch.supplier))
    )
    if severity:
        query = query.filter(QualityAlert.severity == severity)
    if status:
        query = query.filter(QualityAlert.status == status)

    alerts = query.order_by(QualityAlert.created_at.desc()).all()

    headers = [
        "预警ID", "批次号", "供应商",
        "预警类型", "严重程度", "处理状态",
        "预警描述",
        "港口检测值", "入厂检测值", "绝对偏差", "相对偏差率", "触发阈值",
        "处理人", "处理时间", "处理备注",
        "创建时间",
    ]

    rows = []
    for a in alerts:
        batch_number = a.batch.batch_number if a.batch else ""
        supplier_name = a.batch.supplier.name if a.batch and a.batch.supplier else ""
        rows.append([
            a.id,
            batch_number,
            supplier_name,
            a.alert_type,
            a.severity,
            a.status,
            a.description,
            a.port_value if a.port_value is not None else "",
            a.factory_value if a.factory_value is not None else "",
            a.deviation if a.deviation is not None else "",
            round(a.deviation_rate * 100, 3) if a.deviation_rate is not None else "",
            a.threshold_value if a.threshold_value is not None else "",
            a.resolved_by or "",
            a.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if a.resolved_at else "",
            a.resolution_notes or "",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
        ])

    filename = f"alerts_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    return _make_csv_response(rows, headers, filename)
