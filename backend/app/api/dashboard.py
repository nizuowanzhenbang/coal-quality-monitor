"""看板统计接口"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.batch import CoalBatch, BatchStatus
from app.models.alert import QualityAlert, AlertType, Severity, AlertStatus
from app.models.supplier import Supplier
from app.models.test import QualityTest, TestType
from app.models.user import User
from app.utils.helpers import api_response

router = APIRouter(prefix="/api/dashboard", tags=["看板统计"])


@router.get("/overview", response_model=dict, summary="总览统计")
def overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    返回：总批次数/今日批次/待处理预警/严重预警/异常率/平均热值偏差/供应商数
    """
    today_start = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=0, minute=0, second=0, microsecond=0)

    total_batches = db.query(func.count(CoalBatch.id)).scalar() or 0
    today_batches = (
        db.query(func.count(CoalBatch.id))
        .filter(CoalBatch.created_at >= today_start)
        .scalar() or 0
    )
    pending_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(QualityAlert.status == AlertStatus.PENDING)
        .scalar() or 0
    )
    severe_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(
            QualityAlert.severity == Severity.SEVERE,
            QualityAlert.status == AlertStatus.PENDING,
        )
        .scalar() or 0
    )

    anomaly_batches = (
        db.query(func.count(CoalBatch.id))
        .filter(CoalBatch.status.in_([BatchStatus.ALERT, BatchStatus.SEVERE]))
        .scalar() or 0
    )
    completed_batches = (
        db.query(func.count(CoalBatch.id))
        .filter(CoalBatch.status.in_([BatchStatus.COMPLETED, BatchStatus.ALERT, BatchStatus.SEVERE]))
        .scalar() or 0
    )
    anomaly_rate = round(anomaly_batches / completed_batches, 4) if completed_batches else 0.0

    # 平均热值偏差（港口-入厂，kcal/kg）
    port_cal_avg = (
        db.query(func.avg(QualityTest.calorific_value_net))
        .filter(QualityTest.test_type == TestType.PORT, QualityTest.calorific_value_net.isnot(None))
        .scalar()
    )
    factory_cal_avg = (
        db.query(func.avg(QualityTest.calorific_value_net))
        .filter(QualityTest.test_type == TestType.FACTORY, QualityTest.calorific_value_net.isnot(None))
        .scalar()
    )
    avg_cal_deviation = None
    if port_cal_avg and factory_cal_avg:
        avg_cal_deviation = round(float(port_cal_avg) - float(factory_cal_avg), 1)

    total_suppliers = db.query(func.count(Supplier.id)).scalar() or 0
    active_suppliers = (
        db.query(func.count(Supplier.id))
        .filter(Supplier.status == "ACTIVE")
        .scalar() or 0
    )

    return api_response(data={
        "total_batches": total_batches,
        "today_batches": today_batches,
        "pending_alerts": pending_alerts,
        "severe_alerts": severe_alerts,
        "anomaly_rate": anomaly_rate,
        "avg_calorific_deviation": avg_cal_deviation,
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
    })


@router.get("/quality-trend", response_model=dict, summary="近N天各指标平均偏差趋势")
def quality_trend(
    days: int = Query(30, ge=7, le=180, description="统计天数"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按日分组，返回各指标平均偏差"""
    start_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    # 查询时间范围内有双端化验的批次
    batches = (
        db.query(CoalBatch)
        .filter(
            CoalBatch.created_at >= start_date,
            CoalBatch.status.in_([BatchStatus.COMPLETED, BatchStatus.ALERT, BatchStatus.SEVERE]),
        )
        .all()
    )

    # 按日期聚合偏差数据
    daily: dict = {}
    for batch in batches:
        day_key = batch.created_at.strftime("%Y-%m-%d") if batch.created_at else "unknown"
        port_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == batch.id, QualityTest.test_type == TestType.PORT)
            .first()
        )
        factory_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == batch.id, QualityTest.test_type == TestType.FACTORY)
            .first()
        )
        if not port_t or not factory_t:
            continue

        if day_key not in daily:
            daily[day_key] = {
                "date": day_key,
                "cal_devs": [], "ash_devs": [], "sulfur_devs": [], "moisture_devs": [],
                "count": 0,
            }
        entry = daily[day_key]
        entry["count"] += 1

        if port_t.calorific_value_net and factory_t.calorific_value_net and port_t.calorific_value_net > 0:
            entry["cal_devs"].append(
                (port_t.calorific_value_net - factory_t.calorific_value_net) / port_t.calorific_value_net * 100
            )
        if port_t.ash_content is not None and factory_t.ash_content is not None:
            entry["ash_devs"].append(factory_t.ash_content - port_t.ash_content)
        if port_t.sulfur_content is not None and factory_t.sulfur_content is not None:
            entry["sulfur_devs"].append(factory_t.sulfur_content - port_t.sulfur_content)
        if port_t.moisture_total is not None and factory_t.moisture_total is not None:
            entry["moisture_devs"].append(factory_t.moisture_total - port_t.moisture_total)

    trend = []
    for day_key in sorted(daily.keys()):
        e = daily[day_key]
        trend.append({
            "date": e["date"],
            "batch_count": e["count"],
            "avg_calorific_deviation_pct": round(sum(e["cal_devs"]) / len(e["cal_devs"]), 3) if e["cal_devs"] else None,
            "avg_ash_deviation": round(sum(e["ash_devs"]) / len(e["ash_devs"]), 3) if e["ash_devs"] else None,
            "avg_sulfur_deviation": round(sum(e["sulfur_devs"]) / len(e["sulfur_devs"]), 4) if e["sulfur_devs"] else None,
            "avg_moisture_deviation": round(sum(e["moisture_devs"]) / len(e["moisture_devs"]), 3) if e["moisture_devs"] else None,
        })

    return api_response(data={"days": days, "trend": trend})


@router.get("/supplier-ranking", response_model=dict, summary="供应商信用分排名")
def supplier_ranking(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """供应商按信用分排名，附批次数和异常率"""
    suppliers = db.query(Supplier).order_by(Supplier.credit_score.desc()).all()

    ranking = []
    for s in suppliers:
        total = db.query(func.count(CoalBatch.id)).filter(CoalBatch.supplier_id == s.id).scalar() or 0
        anomaly = (
            db.query(func.count(CoalBatch.id))
            .filter(
                CoalBatch.supplier_id == s.id,
                CoalBatch.status.in_([BatchStatus.ALERT, BatchStatus.SEVERE]),
            )
            .scalar() or 0
        )
        ranking.append({
            "supplier_id": s.id,
            "supplier_name": s.name,
            "credit_score": s.credit_score,
            "status": s.status,
            "total_batches": total,
            "anomaly_batches": anomaly,
            "anomaly_rate": round(anomaly / total, 4) if total else 0.0,
        })

    return api_response(data=ranking)


@router.get("/alert-distribution", response_model=dict, summary="预警类型分布")
def alert_distribution(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """各预警类型数量分布（全部 + 仅严重）"""
    rows = (
        db.query(QualityAlert.alert_type, QualityAlert.severity, func.count(QualityAlert.id).label("cnt"))
        .group_by(QualityAlert.alert_type, QualityAlert.severity)
        .all()
    )
    distribution = {}
    for row in rows:
        key = row.alert_type
        if key not in distribution:
            distribution[key] = {"alert_type": key, "total": 0, "general": 0, "severe": 0}
        distribution[key]["total"] += row.cnt
        if row.severity == Severity.GENERAL:
            distribution[key]["general"] += row.cnt
        else:
            distribution[key]["severe"] += row.cnt

    return api_response(data=list(distribution.values()))


@router.get("/calorific-scatter", response_model=dict, summary="热值散点图数据")
def calorific_scatter(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回港口热值 vs 入厂热值的散点图数据，带批次号/供应商名"""
    batches = (
        db.query(CoalBatch)
        .filter(CoalBatch.status.in_([BatchStatus.COMPLETED, BatchStatus.ALERT, BatchStatus.SEVERE]))
        .all()
    )

    points = []
    for batch in batches:
        port_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == batch.id, QualityTest.test_type == TestType.PORT)
            .first()
        )
        factory_t = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == batch.id, QualityTest.test_type == TestType.FACTORY)
            .first()
        )
        if not port_t or not factory_t:
            continue
        if not port_t.calorific_value_net or not factory_t.calorific_value_net:
            continue

        supplier_name = ""
        if batch.supplier:
            supplier_name = batch.supplier.name
        else:
            s = db.query(Supplier).filter(Supplier.id == batch.supplier_id).first()
            supplier_name = s.name if s else ""

        points.append({
            "batch_id": batch.id,
            "batch_number": batch.batch_number,
            "supplier_name": supplier_name,
            "port_calorific": port_t.calorific_value_net,
            "factory_calorific": factory_t.calorific_value_net,
            "deviation": round(port_t.calorific_value_net - factory_t.calorific_value_net, 1),
            "status": batch.status,
            "risk_score": batch.risk_score,
        })

    return api_response(data={"count": len(points), "points": points})
