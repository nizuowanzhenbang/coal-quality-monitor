"""Transport alerts survive real manual and automatic quality API evaluations."""
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
from app.models.batch import CoalBatch
from app.models.supplier import Supplier
from app.models.user import User, UserRole


TRANSPORT_TYPES = {"TRANSPORT_WEIGHT", "TRANSPORT_TIME", "TRANSPORT_SEAL"}


@pytest.fixture
def transport_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "SECRET_KEY", "local-transport-api-test-jwt")
    monkeypatch.setattr(settings, "INTEGRATION_SECRET", "local-transport-api-test-secret")
    monkeypatch.setattr(integration, "SessionLocal", session_factory)

    with session_factory() as db:
        supplier = Supplier(name="API transport supplier", credit_score=100)
        db.add(supplier)
        db.flush()
        batch = CoalBatch(batch_number="API-TRANSPORT-001", supplier_id=supplier.id)
        db.add(batch)
        for username, role in (("api-operator", UserRole.OPERATOR), ("api-viewer", UserRole.VIEWER)):
            db.add(User(username=username, role=role, hashed_password="unused-test-hash", is_active=True))
        db.commit()
        batch_id, supplier_id = batch.id, supplier.id

    def isolated_db():
        with session_factory() as db:
            yield db

    def auth_headers(username):
        token = jwt.encode(
            {"sub": username, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )
        return {"Authorization": f"Bearer {token}"}

    app = FastAPI()
    for router in (batches.router, lab_tests.router, integration.router, alerts.router, suppliers.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, headers=auth_headers("api-operator")) as client:
            yield SimpleNamespace(
                client=client, batch_id=batch_id, supplier_id=supplier_id,
                viewer_headers=auth_headers("api-viewer"),
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _data(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _create_lab(api, kind, *, ash=15):
    return _data(api.client.post("/api/tests", json={
        "batch_id": api.batch_id, "test_type": kind,
        "calorific_value_net": 6000, "ash_content": ash,
    }))


def _transport_event(api, *, all_types=False):
    items = [{"alert_type": "SEAL_DAMAGED", "severity": "SEVERE", "description": "seal damaged"}]
    if all_types:
        items.extend([
            {"alert_type": "WEIGHT_SHORTAGE", "severity": "GENERAL", "description": "weight shortage"},
            {"alert_type": "TIME_EXCESSIVE", "severity": "GENERAL", "description": "late arrival"},
        ])
    response = api.client.post(
        "/api/integration/transport-event",
        headers={"X-Integration-Secret": settings.INTEGRATION_SECRET},
        json={
            "batch_number": "API-TRANSPORT-001", "departure_net_weight": 100,
            "arrival_net_weight": 98, "weight_diff_ratio": 0.02,
            "alerts": [dict(item, threshold_value=0.01, actual_value=0.02) for item in items],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["alerts_created"] == len(items)


def _transport_rows(api):
    items = _data(api.client.get("/api/alerts", params={"page_size": 100}))["items"]
    return {item["id"]: item for item in items if item["alert_type"] in TRANSPORT_TYPES}


def _assert_summary(api, *, count, risk, score):
    detail = _data(api.client.get(f"/api/batches/{api.batch_id}"))
    listed = _data(api.client.get("/api/batches"))["items"][0]
    assert len(detail["alerts"]) == count
    for summary in (detail, listed):
        assert summary["status"] == "SEVERE"
        assert summary["alert_count"] == count
        assert summary["risk_score"] == pytest.approx(risk)
    stats = _data(api.client.get("/api/alerts/stats"))
    assert stats["total"] == count
    assert stats["by_type"]["TRANSPORT_SEAL"] == 1
    recalculated = _data(api.client.post(f"/api/suppliers/{api.supplier_id}/recalculate-score"))
    assert recalculated["credit_score"] == score
    supplier = _data(api.client.get(f"/api/suppliers/{api.supplier_id}"))
    assert supplier["credit_score"] == score
    assert supplier["total_alerts"] == count
    assert supplier["recent_batches"][0]["alert_count"] == count


def test_manual_evaluation_twice_retains_all_transport_rows_and_combines_summaries(transport_api):
    api = transport_api
    _create_lab(api, "PORT")
    _create_lab(api, "FACTORY", ash=16)
    _transport_event(api, all_types=True)
    before = _transport_rows(api)
    assert {row["alert_type"] for row in before.values()} == TRANSPORT_TYPES

    for _ in range(2):
        evaluation = _data(api.client.post(f"/api/batches/{api.batch_id}/evaluate"))
        assert _transport_rows(api) == before
        assert [row["alert_type"] for row in evaluation["alerts"]] == ["ASH_EXCESS"]
        assert evaluation["alert_count"] == 4
        assert evaluation["risk_score"] == pytest.approx(1.35)
        _assert_summary(api, count=4, risk=1.35, score=92)


def test_transport_before_second_lab_survives_automatic_evaluation(transport_api):
    api = transport_api
    _create_lab(api, "PORT")
    _transport_event(api)
    before = _transport_rows(api)
    _create_lab(api, "FACTORY")
    assert _transport_rows(api) == before
    _assert_summary(api, count=1, risk=0.6, score=95)


def test_lab_update_clears_quality_alert_but_retains_transport_alert(transport_api):
    api = transport_api
    _create_lab(api, "PORT")
    factory = _create_lab(api, "FACTORY", ash=16)
    _transport_event(api)
    before = _transport_rows(api)
    _data(api.client.put(f"/api/tests/{factory['id']}", json={"ash_content": 15}))
    assert _transport_rows(api) == before
    _assert_summary(api, count=1, risk=0.6, score=95)


@pytest.mark.parametrize("handling", ["acknowledge", "resolve"])
def test_evaluation_preserves_transport_handling_history(transport_api, handling):
    api = transport_api
    _create_lab(api, "PORT")
    _create_lab(api, "FACTORY")
    _transport_event(api)
    alert_id = next(iter(_transport_rows(api)))
    _data(api.client.put(f"/api/alerts/{alert_id}/acknowledge"))
    if handling == "resolve":
        _data(api.client.put(
            f"/api/alerts/{alert_id}/resolve", json={"resolution_notes": "seal inspected and recorded"},
        ))
    before = _transport_rows(api)
    row = before[alert_id]
    assert row["status"] == ("RESOLVED" if handling == "resolve" else "ACKNOWLEDGED")
    assert row["resolved_by"] == "api-operator"
    assert row["resolved_at"] is not None
    if handling == "resolve":
        assert row["resolution_notes"] == "seal inspected and recorded"

    _data(api.client.post(f"/api/batches/{api.batch_id}/evaluate"))
    assert _transport_rows(api) == before
    # Existing scoring counts severe alerts even after resolution.
    _assert_summary(api, count=1, risk=0.6, score=95)


def test_viewer_and_wrong_integration_secret_cannot_mutate_alerts(transport_api):
    api = transport_api
    _create_lab(api, "PORT")
    factory = _create_lab(api, "FACTORY")
    _transport_event(api)
    before = _transport_rows(api)
    response = api.client.post(f"/api/batches/{api.batch_id}/evaluate", headers=api.viewer_headers)
    assert response.status_code == 403
    response = api.client.put(
        f"/api/tests/{factory['id']}", headers=api.viewer_headers, json={"ash_content": 50},
    )
    assert response.status_code == 403
    response = api.client.post(
        "/api/integration/transport-event", headers={"X-Integration-Secret": "wrong-local-secret"},
        json={"batch_number": "API-TRANSPORT-001", "alerts": []},
    )
    assert response.status_code == 403
    assert _transport_rows(api) == before
    assert _data(api.client.get(f"/api/tests/{factory['id']}"))["ash_content"] == 15
