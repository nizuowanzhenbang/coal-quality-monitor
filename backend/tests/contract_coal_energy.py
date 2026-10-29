"""显式运行的双应用契约：合成煤质记录 → 实际能效预览。"""
import json
import os
from pathlib import Path
import subprocess

from tests.test_lab_finite_values import api, create  # noqa: F401
from app.config import settings


def test_real_export_to_energy_preview(api, monkeypatch, tmp_path):
    monkeypatch.setitem(settings.__dict__, 'QUALITY_SOURCE_INSTANCE', 'synthetic-instance-a')
    lab = create(api, 'FACTORY', {'calorific_value_net': 4000, 'test_time': '2026-10-28T08:00:00'})
    url = f"/api/tests/{lab['id']}/energy-measurement"
    assert api.client.post(url, json={}).status_code == 422
    response = api.client.post(url, json={'offset_minutes': 480, 'time_evidence': '合成实验室记录：UTC+08'})
    assert response.status_code == 200, response.text
    export = response.json()['data']
    assert export['measurement'] == {
        'source_system': 'coal-quality-monitor', 'source_instance': 'synthetic-instance-a',
        'batch_id': str(api.batch_id), 'test_id': str(lab['id']), 'metric': 'Qnet',
        'basis': 'ar', 'unit': 'kcal/kg', 'value': 4000,
        'measured_at': '2026-10-28T08:00:00+08:00',
    }
    assert export['time_provenance'] == {'kind': 'caller_declared_offset', 'offset_minutes': 480,
                                         'evidence': '合成实验室记录：UTC+08',
                                         'stored_time': '2026-10-28T08:00:00'}
    peer_root = Path(os.environ['ENERGY_PEER_ROOT']).resolve(strict=True)
    peer_python = Path(os.environ['ENERGY_PEER_PYTHON']).absolute()
    assert peer_python.is_file(), '能效Python环境不存在'
    env = os.environ.copy()
    env.update(PYTHONPATH=str(peer_root / 'backend'), CUE_DATABASE_URL=f"sqlite:///{tmp_path / 'energy.db'}",
               CUE_ENABLE_SCHEDULER='false', CUE_AUTO_SEED='false')
    result = subprocess.run([str(peer_python), str(Path(__file__).with_name('energy_peer.py'))],
                            cwd=peer_root / 'backend', env=env,
                            input=json.dumps(export, ensure_ascii=False), capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome['heat'] == 16747.2
    assert outcome['measurement'] == export['measurement']
    assert outcome['snapshot_count'] == 0
    assert outcome['wrong_instance'] == outcome['wrong_batch'] == outcome['wrong_basis'] == 422

    assert outcome['evidence']['measurement'] == export['measurement']
    assert outcome['evidence']['time_provenance'] == export['time_provenance']
    assert outcome['evidence']['created_by'] == 'contract'
    assert outcome['evidence']['kind'] == 'operator_submitted'
