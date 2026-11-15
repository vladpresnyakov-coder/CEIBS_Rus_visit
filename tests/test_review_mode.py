"""Private owner-only review is opt-in, capability-protected, never public."""
import io
from flask import Flask
from final_registration import init_final_registration
from test_final_registration import harness, png, payload


def review_service(harness, monkeypatch, token='s'*48):
    monkeypatch.setenv('FINAL_REGISTRATION_REVIEW_MODE', '1')
    monkeypatch.setenv('FINAL_REGISTRATION_REVIEW_TOKEN', token)
    monkeypatch.setenv('FINAL_REGISTRATION_TELEGRAM_CHAT_IDS', '[111111111]')
    app = Flask('private-review', static_folder=None)
    service = init_final_registration(app, None, harness.connection, False)
    service.clock = harness.service.clock
    sent = []
    service.transport.send_document = lambda *args: sent.append(args)
    return app.test_client(), service, sent


def test_private_review_one_recipient_requires_secret_on_every_request(harness, monkeypatch):
    from test_final_registration import group
    group(harness, 2, 'Synthetic Nonreview Participant')
    assert harness.service.run_once() and harness.service.run_once()
    client, service, sent = review_service(harness, monkeypatch)
    assert client.get('/api/final-register/config').json['enabled'] is False
    assert client.post('/api/final-register/drafts', json={'lang':'ru'}).status_code == 503
    assert client.get('/api/final-register/config', headers={'X-Registration-Review':'wrong'}).json['enabled'] is False
    headers = {'X-Registration-Review':'s'*48}
    ready = client.get('/api/final-register/config', headers=headers).json
    assert ready['enabled'] is True and ready['reviewMode'] is True
    draft = client.post('/api/final-register/drafts', headers=headers, json={'lang':'ru'}).json
    upload_url = f"/api/final-register/drafts/{draft['draftId']}/passport"
    auth = {**headers, 'Authorization':'Bearer '+draft['token']}
    assert client.post(upload_url, headers={'Authorization':auth['Authorization']}).status_code == 503
    scan = client.post(upload_url, headers=auth, data={'file':(io.BytesIO(png()),'synthetic.png','image/png')})
    assert scan.status_code == 200
    data = payload([scan.json['passportId']])
    submit_url = f"/api/final-register/drafts/{draft['draftId']}/submit"
    assert client.post(submit_url, headers=auth, json=data).status_code == 200
    assert service.run_once() and not service.run_once()
    assert len(sent)==2 and all(item[0]==111111111 for item in sent)
    from openpyxl import load_workbook
    assert load_workbook(io.BytesIO(sent[0][2])).active.max_row == 2


def test_review_missing_or_short_token_fails_closed(harness, monkeypatch):
    for token in ('', 'short'):
        client, service, _ = review_service(harness, monkeypatch, token)
        assert client.get('/api/final-register/config',headers={'X-Registration-Review':token}).json['enabled'] is False
        assert not service.enabled
