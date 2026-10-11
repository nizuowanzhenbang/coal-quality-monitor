"""真实 HTTP 回归：单位/基准/缺项/范围及不可表示的相对偏差。"""
import pytest

from tests.test_lab_finite_values import api, NORMAL, METRICS, create, data, prepare, assert_rejected, snapshot
from app.models.alert import QualityAlert


BASES = dict(zip(METRICS, ('ar', 'ad', 'd', 'd', 'ar', 'ad', 'd', 'd')))
CORE = ('calorific_value_net', 'ash_content', 'sulfur_content', 'moisture_total')


@pytest.mark.parametrize('operation', ['create', 'update'])
@pytest.mark.parametrize('field', METRICS)
@pytest.mark.parametrize('side', ['below', 'above'])
def test_ranges_reject_entire_request_and_preserve_transport(api, operation, field, side):
    url, payload = prepare(api, operation)
    payload[field] = -0.01 if side == 'below' else (10001 if field.startswith('calorific') else 100.01)
    assert_rejected(api, operation, url, payload, field)


@pytest.mark.parametrize('operation', ['create', 'update'])
@pytest.mark.parametrize('field', ['contract_calorific_value', 'contract_ash_max',
                                  'contract_sulfur_max', 'contract_moisture_max'])
@pytest.mark.parametrize('value', [-1, 'Infinity', 1e308])
def test_contract_measurements_reject_invalid_values_before_writing(api, operation, field, value):
    before = snapshot(api)
    url = '/api/batches' if operation == 'create' else f'/api/batches/{api.batch_id}'
    payload = {'batch_number': 'INVALID', 'supplier_id': api.supplier_id} if operation == 'create' else {}
    response = api.client.request('POST' if operation == 'create' else 'PUT', url,
                                  json={**payload, 'notes': 'must not save', field: value})
    assert response.status_code == 422, response.text
    assert snapshot(api) == before


def test_mj_conversion_and_partial_update_never_reconvert_old_values(api):
    result = create(api, 'PORT', {'calorific_value_unit': 'MJ/kg',
                                 'calorific_value_net': '25.1208', 'calorific_value_gross': 25.95816})
    assert result['calorific_value_net'] == pytest.approx(6000)
    assert result['calorific_value_gross'] == pytest.approx(6200)
    assert result['calorific_value_unit'] == 'kcal/kg'
    assert result['measurement_bases'] == BASES
    assert result['measurement_units']['ash_content'] == '%'
    url = f"/api/tests/{result['id']}"
    for payload in [{'calorific_value_unit': 'MJ/kg', 'notes': 'metadata alone'},
                    {'calorific_value_unit': 'MJ/kg', 'calorific_value_net': 25.1208},
                    {'calorific_value_net': 6000}, {'ash_content': 15}]:
        result = data(api.client.put(url, json=payload))
        assert result['calorific_value_net'] == pytest.approx(6000)
        assert result['calorific_value_gross'] == pytest.approx(6200)
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['port_test']['measurement_bases'] == BASES


@pytest.mark.parametrize('operation', ['create', 'update'])
@pytest.mark.parametrize('payload,field', [({'calorific_value_unit': 'kJ/kg'}, 'calorific_value_unit'),
    ({'calorific_value_unit': 'MJ/kg', 'calorific_value_net': 42}, 'calorific_value_net'),
    ({'measurement_bases': {'ash_content': 'ar'}}, 'measurement_bases'),
    ({'measurement_bases': {'unknown': 'd'}}, 'measurement_bases')])
def test_unsupported_metadata_or_converted_range_rejected_without_side_effects(api, operation, payload, field):
    url, body = prepare(api, operation)
    assert_rejected(api, operation, url, {**body, **payload}, field)


def test_explicit_canonical_bases_and_upper_bound_are_accepted(api):
    result = create(api, 'PORT', {'measurement_bases': BASES, 'calorific_value_unit': 'MJ/kg',
                                 'calorific_value_net': 41.868, 'ash_content': 100})
    assert result['calorific_value_net'] == pytest.approx(10000)
    assert result['measurement_bases'] == BASES


def test_two_empty_records_are_partial_with_explicit_missing_fields(api):
    create(api, 'PORT', {})
    create(api, 'FACTORY', {})
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['status'] == 'PARTIAL'
    assert detail['assessment'] == {'complete': False, 'missing_by_source': {'PORT': list(CORE), 'FACTORY': list(CORE)}}
    result = data(api.client.post(f'/api/batches/{api.batch_id}/evaluate'))
    assert result['status'] == 'PARTIAL'
    assert result['assessment'] == detail['assessment']


@pytest.mark.parametrize('kind', ['PORT', 'FACTORY'])
@pytest.mark.parametrize('field', CORE)
def test_clearing_a_core_measurement_makes_assessment_partial(api, kind, field):
    records = {source: create(api, source, NORMAL) for source in ['PORT', 'FACTORY']}
    data(api.client.put(f"/api/tests/{records[kind]['id']}", json={field: None}))
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['status'] == 'PARTIAL'
    assert detail['assessment']['missing_by_source'][kind] == [field]
    assert detail['assessment']['complete'] is False


def test_partial_assessment_preserves_transport_resolution_and_severity(api):
    url, _ = prepare(api, 'update')
    before = data(api.client.get('/api/alerts'))['items']
    retained = next(a for a in before if a['alert_type'] == 'TRANSPORT_SEAL')
    data(api.client.put(url, json={'ash_content': None}))
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['status'] == 'SEVERE'
    assert detail['assessment']['complete'] is False
    assert next(a for a in data(api.client.get('/api/alerts'))['items']
                if a['id'] == retained['id']) == retained


def test_zero_factory_heat_triggers_loss_and_contract_alert(api):
    data(api.client.put(f'/api/batches/{api.batch_id}', json={'contract_calorific_value': 5800}))
    create(api, 'PORT', NORMAL)
    create(api, 'FACTORY', {**NORMAL, 'calorific_value_net': 0})
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['assessment']['complete'] is True
    types = {a['alert_type'] for a in detail['alerts']}
    assert {'CALORIFIC_SHORTAGE', 'CONTRACT_CAL_BREACH'} <= types


@pytest.mark.parametrize('field', ['ash_content', 'sulfur_content', 'moisture_total',
                                  'volatile_matter', 'calorific_value_net'])
def test_subnormal_baseline_has_json_safe_ratios_and_retains_absolute_alerts(api, field):
    create(api, 'PORT', {**NORMAL, field: 5e-324})
    create(api, 'FACTORY', {**NORMAL, field: 20})
    detail = data(api.client.get(f'/api/batches/{api.batch_id}'))
    assert detail['comparison'][field]['deviation_rate'] is None
    if field in ['ash_content', 'sulfur_content', 'moisture_total']:
        assert detail['alerts']
        assert all(a['deviation_rate'] is None for a in detail['alerts'])
        with api.factory() as db:
            assert all(a.deviation_rate is None for a in db.query(QualityAlert).all())
    assert data(api.client.get('/api/alerts')) is not None
