"""Explicitly authorized owner-only public intake, with secure defaults intact."""
import io
import pytest
from flask import Flask
from final_registration import init_final_registration
from test_final_registration import harness, png, payload


def public_service(harness, monkeypatch, recipients='[111111111]', allow=True):
    monkeypatch.setenv('FINAL_REGISTRATION_REVIEW_MODE', '0')
    monkeypatch.setenv('FINAL_REGISTRATION_REVIEW_TOKEN', '')
    monkeypatch.setenv('FINAL_REGISTRATION_ALLOW_SINGLE_RECIPIENT', '1' if allow else '0')
    monkeypatch.setenv('FINAL_REGISTRATION_TELEGRAM_CHAT_IDS', recipients)
    app = Flask('owner-only-public', static_folder=None)
    service = init_final_registration(app, None, harness.connection, False)
    service.clock = harness.service.clock
    sent=[]
    service.transport.send_document=lambda *args:sent.append(args)
    return app.test_client(),service,sent


def test_owner_only_public_launch_requires_explicit_permission(harness, monkeypatch):
    closed,_,_=public_service(harness,monkeypatch,allow=False)
    assert closed.get('/api/final-register/config').json['enabled'] is False
    client,service,sent=public_service(harness,monkeypatch)
    config=client.get('/api/final-register/config').json
    assert config['enabled'] is True and 'reviewMode' not in config
    draft=client.post('/api/final-register/drafts',json={'lang':'en'}).json
    auth={'Authorization':'Bearer '+draft['token']}
    scan=client.post(f"/api/final-register/drafts/{draft['draftId']}/passport",headers=auth,
                    data={'file':(io.BytesIO(png()),'synthetic.png','image/png')})
    assert scan.status_code==200
    data=payload([scan.json['passportId']])
    assert client.post(f"/api/final-register/drafts/{draft['draftId']}/submit",headers=auth,json=data).status_code==200
    assert service.run_once() and not service.run_once()
    assert len(sent)==2 and all(entry[0]==111111111 for entry in sent)


@pytest.mark.parametrize('recipients',['[]','[-111111111]','[true]','["111111111"]'])
def test_single_recipient_permission_still_rejects_invalid_private_ids(harness,monkeypatch,recipients):
    client,service,_=public_service(harness,monkeypatch,recipients)
    assert client.get('/api/final-register/config').json['enabled'] is False
    assert not service.enabled
