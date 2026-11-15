"""Exercise the canonical server integration with only synthetic documents."""
import importlib.util
import io
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from PIL import Image
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_server_registers_and_delivers_final_group(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('CEIBS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FINAL_REGISTRATION_ENABLED', '1')
    monkeypatch.setenv('FINAL_REGISTRATION_DISABLE_WORKER', '1')
    monkeypatch.setenv('FINAL_REGISTRATION_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('FINAL_REGISTRATION_TELEGRAM_CHAT_IDS', '[111111111,222222222]')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'synthetic-not-a-real-token')
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('ceibs_canonical_final_test', ROOT / 'server.py')
    assert spec is not None and spec.loader is not None
    site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site)
    client = site.app.test_client()
    response = client.get('/api/final-register/config')
    assert response.status_code == 200
    assert response.json['enabled'] is True
    service = site.app.extensions['final_registration']
    deliveries = []
    service.transport.send_document = lambda *args: deliveries.append(args)
    draft = client.post('/api/final-register/drafts', json={'lang': 'ru'}).json
    headers = {'Authorization': 'Bearer ' + draft['token']}
    image = io.BytesIO()
    Image.new('RGB', (64, 64), 'white').save(image, 'PNG')
    people = []
    for number in range(2):
        uploaded = client.post(f"/api/final-register/drafts/{draft['draftId']}/passport", headers=headers,
                               data={'file': (io.BytesIO(image.getvalue()), 'synthetic.png', 'image/png')})
        assert uploaded.status_code == 200
        people.append({'fullName': f'Synthetic Participant {number}', 'passportId': uploaded.json['passportId']})
    trip = {'city': 'Synthetic City', 'date': '2027-01-24', 'time': '12:00', 'flight': 'TEST001'}
    payload = {'lang': 'ru', 'people': people, 'arrival': trip, 'departure': {**trip, 'date': '2027-01-31'},
               'singleRoom': None, 'paymentMethod': 'alipay', 'privacyConsent': True}
    endpoint = f"/api/final-register/drafts/{draft['draftId']}/submit"
    result = client.post(endpoint, headers=headers, json=payload)
    assert result.status_code == 200 and result.json['participantsCount'] == 2
    assert client.post(endpoint, headers=headers, json=payload).json['registrationId'] == result.json['registrationId']
    assert service.run_once() and service.run_once() and not service.run_once()
    assert len(deliveries) == 6
    for recipient in (111111111, 222222222):
        files = [entry for entry in deliveries if entry[0] == recipient]
        assert len(files) == 3
        workbook = load_workbook(io.BytesIO(files[0][2]))
        assert workbook.active.max_row == 3
    with site._sqlite_conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM pre_registrations').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM final_registrations').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM final_outbox WHERE done=1').fetchone()[0] == 2
    assert client.get('/final_registration.py').status_code == 404
    assert client.get('/api/final-register/config').headers['Cache-Control'] == 'no-store, private'
