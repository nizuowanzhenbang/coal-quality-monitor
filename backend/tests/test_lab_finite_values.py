"""真实化验接口拒绝非有限值，保留既有数据与缺省字段语义。"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import alerts, batches, integration, suppliers, tests as lab_tests
from app.api.deps import get_db
from app.config import settings
from app.database import Base
from app.models.alert import QualityAlert
from app.models.batch import CoalBatch
from app.models.supplier import Supplier
from app.models.test import QualityTest
from app.models.user import User, UserRole


METRICS = (
    "calorific_value_net", "calorific_value_gross", "ash_content", "sulfur_content",
    "moisture_total", "moisture_inherent", "volatile_matter", "fixed_carbon",
)
NORMAL = dict(zip(METRICS, (6000, 6200, 15, 0.5, 8, 2, 25, 55)))


@pytest.fixture
def api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "SECRET_KEY", "lab-finite-test-key")
    monkeypatch.setattr(settings, "INTEGRATION_SECRET", "lab-finite-test-integration")
    monkeypatch.setattr(integration, "SessionLocal", factory)
    with factory() as db:
        supplier = Supplier(name="模拟煤质供应商", credit_score=100)
        db.add(supplier)
        db.flush()
        batch = CoalBatch(batch_number="FINITE-001", supplier_id=supplier.id)
        db.add_all([batch, CoalBatch(batch_number="OTHER-001", supplier_id=supplier.id)])
        for username, role in (("operator", UserRole.OPERATOR), ("viewer", UserRole.VIEWER)):
            db.add(User(username=username, role=role, hashed_password="unused", is_active=True))
        db.commit()
        batch_id, supplier_id = batch.id, supplier.id

    def isolated_db():
        with factory() as db:
            yield db

    def headers(username):
        token = jwt.encode(
            {"sub": username, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )
        return {"Authorization": "Bearer " + token}

    app = FastAPI()
    for router in (lab_tests.router, batches.router, alerts.router, suppliers.router, integration.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, headers=headers("operator"), raise_server_exceptions=False) as client:
            yield SimpleNamespace(client=client, factory=factory, batch_id=batch_id,
                                  supplier_id=supplier_id, viewer_headers=headers("viewer"))
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def data(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def create(api, kind, values):
    return data(api.client.post("/api/tests", json={
        "batch_id": api.batch_id, "test_type": kind, **values,
    }))


def score(api):
    return data(api.client.post(f"/api/suppliers/{api.supplier_id}/recalculate-score"))["credit_score"]


def prepare(api, operation):
    """从真实接口建立已有化验和已处理运输预警，更新场景额外含质量预警。"""
    create(api, "PORT", NORMAL)
    response = api.client.post("/api/integration/transport-event", headers={
        "X-Integration-Secret": settings.INTEGRATION_SECRET,
    }, json={"batch_number": "FINITE-001", "alerts": [{
        "alert_type": "SEAL_DAMAGED", "severity": "SEVERE",
        "description": "模拟铅封异常", "threshold_value": 0, "actual_value": 1,
    }]})
    assert response.status_code == 200, response.text
    alert_id = data(api.client.get("/api/alerts"))["items"][0]["id"]
    data(api.client.put(f"/api/alerts/{alert_id}/resolve", json={"resolution_notes": "模拟复核已记录"}))
    if operation == "create":
        assert score(api) == 95
        return "/api/tests", {"batch_id": api.batch_id, "test_type": "FACTORY"}
    factory_test = create(api, "FACTORY", {**NORMAL, "ash_content": 16})
    assert score(api) == 92
    return f"/api/tests/{factory_test['id']}", {"notes": "应整体拒绝的修改"}


def snapshot(api):
    """比较全部字段，包含其他批次、处理历史、评分及时间。"""
    with api.factory() as db:
        return {
            model.__tablename__: [
                {column.name: getattr(row, column.name) for column in model.__table__.columns}
                for row in db.query(model).order_by(model.id).all()
            ]
            for model in (QualityTest, CoalBatch, QualityAlert, Supplier)
        }


def assert_rejected(api, operation, url, payload, field, *, raw=False):
    before = snapshot(api)
    detail = data(api.client.get(f"/api/batches/{api.batch_id}"))
    expected_score = score(api)
    method = "POST" if operation == "create" else "PUT"
    if raw:
        content = json.dumps(payload).replace('"RAW_OVERFLOW"', "1e309")
        response = api.client.request(method, url, content=content, headers={"Content-Type": "application/json"})
    else:
        response = api.client.request(method, url, json=payload)
    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert snapshot(api) == before
    assert data(api.client.get(f"/api/batches/{api.batch_id}")) == detail
    assert score(api) == expected_score


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("field", METRICS)
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_each_metric_rejects_nonfinite_values_without_side_effects(api, operation, field, value):
    url, payload = prepare(api, operation)
    # 另一合法字段也不能在失败请求中被部分保存。
    payload.update({"notes": "不得保存", "test_org": "不得替换机构", field: value})
    assert_rejected(api, operation, url, payload, field)


@pytest.mark.parametrize("operation", ["create", "update"])
def test_numeric_string_overflow_is_rejected_before_writing(api, operation):
    url, payload = prepare(api, operation)
    payload["calorific_value_net"] = "1e309"
    assert_rejected(api, operation, url, payload, "calorific_value_net")


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("field", METRICS)
def test_json_exponent_overflow_has_serializable_rejection_for_each_metric(api, operation, field):
    url, payload = prepare(api, operation)
    payload[field] = "RAW_OVERFLOW"
    assert_rejected(api, operation, url, payload, field, raw=True)


@pytest.mark.parametrize("values", [NORMAL, dict.fromkeys(METRICS, 0),
                                   {key: str(value) for key, value in NORMAL.items()}],
                         ids=["finite", "zero", "numeric-strings"])
def test_finite_values_and_existing_coercion_round_trip(api, values):
    for kind in ("PORT", "FACTORY"):
        result = create(api, kind, values)
        assert {field: result[field] for field in METRICS} == {key: float(value) for key, value in values.items()}
        with api.factory() as db:
            saved = db.get(QualityTest, result["id"])
            assert {field: getattr(saved, field) for field in METRICS} == {key: float(value) for key, value in values.items()}
    assert data(api.client.get(f"/api/batches/{api.batch_id}"))["status"] == "COMPLETED"
    assert score(api) == 100


@pytest.mark.parametrize("values", [{}, dict.fromkeys(METRICS)], ids=["omitted", "explicit-null"])
def test_optional_measurements_remain_nullable(api, values):
    result = create(api, "PORT", values)
    assert all(result[field] is None for field in METRICS)
    assert data(api.client.get(f"/api/batches/{api.batch_id}"))["status"] == "PARTIAL"


def test_update_omission_preserves_values_and_null_keeps_existing_clear_semantics(api):
    url, _ = prepare(api, "update")
    result = data(api.client.put(url, json={"notes": "只改备注"}))
    assert result["ash_content"] == 16 and result["calorific_value_net"] == 6000
    assert score(api) == 92
    result = data(api.client.put(url, json={"ash_content": None}))
    assert result["ash_content"] is None and result["calorific_value_net"] == 6000
    detail = data(api.client.get(f"/api/batches/{api.batch_id}"))
    assert [alert["alert_type"] for alert in detail["alerts"]] == ["TRANSPORT_SEAL"]
    assert detail["risk_score"] == pytest.approx(0.6)
    assert score(api) == 95


def test_valid_deviation_still_alerts_and_transport_history_survives(api):
    prepare(api, "create")
    create(api, "FACTORY", {**NORMAL, "calorific_value_net": 5800, "ash_content": 16})
    detail = data(api.client.get(f"/api/batches/{api.batch_id}"))
    assert {alert["alert_type"] for alert in detail["alerts"]} == {
        "CALORIFIC_SHORTAGE", "ASH_EXCESS", "TRANSPORT_SEAL",
    }
    transport = next(alert for alert in data(api.client.get("/api/alerts"))["items"]
                     if alert["alert_type"] == "TRANSPORT_SEAL")
    assert transport["status"] == "RESOLVED" and transport["resolution_notes"] == "模拟复核已记录"
    assert detail["status"] == "SEVERE" and detail["alert_count"] == 3
    assert detail["risk_score"] == pytest.approx(1.65)
    assert score(api) == 85


@pytest.mark.parametrize("actor, expected", [("viewer", 403), (None, 401)])
def test_existing_authorization_still_blocks_create_and_update(api, actor, expected):
    create(api, "PORT", NORMAL)
    factory_test = create(api, "FACTORY", NORMAL)
    before = snapshot(api)
    api.client.headers.pop("Authorization")
    if actor:
        api.client.headers.update(api.viewer_headers)
    response = api.client.post("/api/tests", json={"batch_id": api.batch_id, "test_type": "FACTORY"})
    assert response.status_code == expected
    response = api.client.put(f"/api/tests/{factory_test['id']}", json={"ash_content": 16})
    assert response.status_code == expected
    assert snapshot(api) == before
