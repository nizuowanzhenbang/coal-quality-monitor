"""Real database regressions for lab-owned alert replacement and batch summaries."""
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.models.alert import AlertStatus, AlertType, QualityAlert, Severity
from app.models.batch import BatchStatus, CoalBatch
from app.models.test import QualityTest, TestType as LabType
from app.services.quality_engine import QualityEngine
from app.services.supplier_scorer import SupplierScorer


def _tests(db, batch, factory_calorific=6000):
    records = [
        QualityTest(batch_id=batch.id, test_type=LabType.PORT, calorific_value_net=6000),
        QualityTest(batch_id=batch.id, test_type=LabType.FACTORY,
                    calorific_value_net=factory_calorific),
    ]
    db.add_all(records)
    db.commit()
    return records


def _load(db, batch_id):
    db.expire_all()
    return db.query(CoalBatch).options(
        joinedload(CoalBatch.tests), joinedload(CoalBatch.alerts)
    ).filter(CoalBatch.id == batch_id).one()


def _transport(db, batch, kind=AlertType.TRANSPORT_SEAL, severity=Severity.SEVERE):
    alert = QualityAlert(
        batch_id=batch.id, alert_type=kind, severity=severity,
        description='[运输监督] original observation', port_value=100,
        factory_value=98, deviation=2, deviation_rate=0.02, threshold_value=0.01,
        status=AlertStatus.RESOLVED, resolved_by='local-operator',
        resolved_at=datetime(2026, 10, 4, 10), resolution_notes='retained evidence',
    )
    db.add(alert)
    db.commit()
    return alert


def _snapshot(alert):
    return {column.name: getattr(alert, column.name) for column in QualityAlert.__table__.columns}


@pytest.mark.parametrize('kind, risk', [
    (AlertType.TRANSPORT_WEIGHT, 0.70),
    (AlertType.TRANSPORT_TIME, 0.30),
    (AlertType.TRANSPORT_SEAL, 0.60),
])
def test_repeated_clean_evaluation_preserves_transport_evidence(
    db_session, sample_batch, sample_supplier, kind, risk,
):
    _tests(db_session, sample_batch)
    transport = _transport(db_session, sample_batch, kind)
    original = _snapshot(transport)
    for _ in range(2):
        batch = _load(db_session, sample_batch.id)
        created = QualityEngine().evaluate(batch, db_session)
        assert created == []  # Return contains new quality alerts, not retained transport.
        preserved = db_session.get(QualityAlert, original['id'])
        assert preserved is not None
        assert _snapshot(preserved) == original
        assert batch.status == BatchStatus.SEVERE
        assert batch.alert_count == 1
        assert batch.risk_score == pytest.approx(risk)
        assert SupplierScorer().recalculate(sample_supplier, db_session) == 95.0


@pytest.mark.parametrize('factory_calorific, transport_severity, risk, score', [
    (5900, Severity.SEVERE, 1.0, 92.0),
    (5800, Severity.GENERAL, 1.1, 88.0),
])
def test_mixed_alerts_use_both_sources_for_severity_risk_and_supplier_score(
    db_session, sample_batch, sample_supplier, factory_calorific, transport_severity,
    risk, score,
):
    _tests(db_session, sample_batch, factory_calorific)
    transport = _transport(db_session, sample_batch, severity=transport_severity)
    original = _snapshot(transport)
    for _ in range(2):
        batch = _load(db_session, sample_batch.id)
        created = QualityEngine().evaluate(batch, db_session)
        assert [alert.alert_type for alert in created] == [AlertType.CALORIFIC_SHORTAGE]
        assert _snapshot(db_session.get(QualityAlert, original['id'])) == original
        assert batch.status == BatchStatus.SEVERE
        assert batch.alert_count == 2
        assert batch.risk_score == pytest.approx(risk)
        assert len(db_session.query(QualityAlert).filter_by(batch_id=batch.id).all()) == 2
        assert SupplierScorer().recalculate(sample_supplier, db_session) == score


def test_clean_results_remove_all_obsolete_quality_types_only_for_current_batch(
    db_session, sample_batch, sample_supplier,
):
    _tests(db_session, sample_batch)
    transport = _transport(db_session, sample_batch, AlertType.TRANSPORT_TIME, Severity.GENERAL)
    original = _snapshot(transport)
    quality_types = [
        AlertType.CALORIFIC_SHORTAGE, AlertType.ASH_EXCESS, AlertType.SULFUR_EXCESS,
        AlertType.MOISTURE_EXCESS, AlertType.CONTRACT_CAL_BREACH,
        AlertType.CONTRACT_ASH_BREACH, AlertType.CONTRACT_SULFUR_BREACH,
        AlertType.COMPREHENSIVE,
    ]
    db_session.add_all([
        QualityAlert(batch_id=sample_batch.id, alert_type=kind, severity=Severity.SEVERE,
                     description='obsolete quality finding')
        for kind in quality_types
    ])
    other = CoalBatch(batch_number='UNRELATED', supplier_id=sample_supplier.id,
                      status=BatchStatus.SEVERE, alert_count=1, risk_score=0.8)
    db_session.add(other)
    db_session.flush()
    unrelated = QualityAlert(batch_id=other.id, alert_type=AlertType.CALORIFIC_SHORTAGE,
                             severity=Severity.SEVERE, description='unrelated finding')
    db_session.add(unrelated)
    db_session.commit()
    other_id, unrelated_before = other.id, _snapshot(unrelated)
    batch = _load(db_session, sample_batch.id)
    assert QualityEngine().evaluate(batch, db_session) == []
    current = db_session.query(QualityAlert).filter_by(batch_id=batch.id).all()
    assert [_snapshot(alert) for alert in current] == [original]
    assert batch.status == BatchStatus.ALERT
    assert batch.alert_count == 1
    assert batch.risk_score == pytest.approx(0.15)
    assert _snapshot(db_session.get(QualityAlert, unrelated_before['id'])) == unrelated_before
    other = db_session.get(CoalBatch, other_id)
    assert (other.status, other.alert_count, other.risk_score) == (BatchStatus.SEVERE, 1, 0.8)


def test_failed_replacement_rolls_back_alerts_and_batch_summary(db_session, sample_batch):
    _, factory = _tests(db_session, sample_batch, 5900)
    batch = _load(db_session, sample_batch.id)
    QualityEngine().evaluate(batch, db_session)
    _transport(db_session, batch)
    batch.status, batch.alert_count, batch.risk_score = BatchStatus.SEVERE, 2, 1.0
    factory.calorific_value_net = 5800
    db_session.commit()
    before = [_snapshot(a) for a in db_session.query(QualityAlert).order_by(QualityAlert.id)]
    db_session.execute(text('''
        CREATE TRIGGER fail_alert_insert BEFORE INSERT ON quality_alerts
        BEGIN SELECT RAISE(ABORT, 'isolated replacement failure'); END
    '''))
    db_session.commit()
    with pytest.raises(IntegrityError, match='isolated replacement failure'):
        QualityEngine().evaluate(_load(db_session, batch.id), db_session)
    db_session.rollback()
    after = [_snapshot(a) for a in db_session.query(QualityAlert).order_by(QualityAlert.id)]
    assert after == before
    batch = _load(db_session, batch.id)
    assert (batch.status, batch.alert_count, batch.risk_score) == (BatchStatus.SEVERE, 2, 1.0)


def test_missing_second_lab_does_not_rewrite_existing_transport_state(db_session, sample_batch):
    db_session.add(QualityTest(batch_id=sample_batch.id, test_type=LabType.PORT,
                               calorific_value_net=6000))
    db_session.commit()
    transport = _transport(db_session, sample_batch)
    original = _snapshot(transport)
    sample_batch.status, sample_batch.alert_count, sample_batch.risk_score = BatchStatus.SEVERE, 1, 0.6
    db_session.commit()
    batch = _load(db_session, sample_batch.id)
    assert QualityEngine().evaluate(batch, db_session) == []
    assert _snapshot(db_session.get(QualityAlert, original['id'])) == original
    assert (batch.status, batch.alert_count, batch.risk_score) == (BatchStatus.SEVERE, 1, 0.6)
