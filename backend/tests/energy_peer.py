"""隔离子进程：运行固定能效应用，而非模拟端点。"""
from copy import deepcopy
import json
import sys

from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.operation import OperatingSnapshot
from app.models.unit import CoalUnit
from app.models.user import Role, User
from app.security import create_access_token


def main():
    export = json.load(sys.stdin)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(CoalUnit(code='U-TEST', name='合成机组', capacity_mw=600))
        db.add(User(username='contract', full_name='合成', role=Role.ENERGY_ENG.value,
                    hashed_password='unused', is_active=True))
        db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token('contract', Role.ENERGY_ENG.value)}
    measurement = export['measurement']
    body = {
        'contract_version': 'coal-quality-energy/v1', 'measurement': measurement,
        'allocation': {'source_instance': measurement['source_instance'], 'batch_id': measurement['batch_id'],
                       'unit_code': 'U-TEST', 'valid_from': '2026-10-28T00:00:00Z',
                       'valid_to': '2026-10-29T00:00:00Z'},
        'conditions': {'ts': '2026-10-28T01:00:00Z', 'load_mw': 560, 'main_steam_temp': 538,
                       'main_steam_press': 16.7, 'reheat_steam_temp': 538, 'feedwater_temp': 275,
                       'flue_gas_temp': 125, 'flue_o2': 3.6, 'fly_ash_carbon': 2.5,
                       'slag_carbon': 5, 'condenser_vacuum': 4.8, 'ambient_temp': 20,
                       'coal_flow_tph': 240, 'aux_power_mw': 30},
    }
    with TestClient(app) as client:
        response = client.post('/api/integration/coal-quality-preview', json=body, headers=headers)
        assert response.status_code == 200, response.text
        outcome = response.json()
        errors = {}
        for label, section, key, bad in [('wrong_instance', 'allocation', 'source_instance', 'other-instance'),
                                          ('wrong_batch', 'allocation', 'batch_id', 'other-batch'),
                                          ('wrong_basis', 'measurement', 'basis', 'ad')]:
            altered = deepcopy(body)
            altered[section][key] = bad
            errors[label] = client.post('/api/integration/coal-quality-preview', json=altered,
                                        headers=headers).status_code
    with SessionLocal() as db:
        count = db.query(OperatingSnapshot).count()
    print(json.dumps({'heat': outcome['coal_lhv_kj_kg'], 'measurement': outcome['lineage']['measurement'],
                      'snapshot_count': count, **errors}, ensure_ascii=False))


if __name__ == '__main__':
    main()
