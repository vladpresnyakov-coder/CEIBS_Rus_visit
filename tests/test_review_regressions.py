"""Regressions for real independently reproduced export and retention defects."""
import copy
import time
import pytest
from flask import Flask
from final_registration import FinalRegistration, RETENTION_TIMESTAMP, init_final_registration
from test_final_registration import harness, draft, upload, payload, submit, group


@pytest.mark.parametrize('character', ['\ufffe', '\uffff', '\ud800'])
@pytest.mark.parametrize('field', ['fullName', 'arrivalCity', 'phone'])
def test_xml_unrepresentable_text_is_rejected_before_persistence(harness, character, field):
    d = draft(harness)
    data = payload([upload(harness, d).json['passportId']])
    if field == 'fullName':
        data['people'][0]['fullName'] = 'Synthetic ' + character + ' Person'
    elif field == 'arrivalCity':
        data['arrival']['city'] = 'Synthetic ' + character + ' City'
    else:
        data['phone'] = '123' + character
    assert submit(harness, d, data).status_code == 400
    with harness.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM final_registrations').fetchone()[0] == 0
    data = payload([data['people'][0]['passportId']])
    assert submit(harness, d, data).status_code == 200
    assert harness.service.run_once() and harness.service.run_once()
    from openpyxl import load_workbook
    import io
    for entry in harness.sent:
        if entry[1].endswith('.xlsx'):
            assert load_workbook(io.BytesIO(entry[2])).active.max_row == 2


def test_disabled_intake_still_starts_maintenance_and_purges(harness, monkeypatch):
    group(harness)
    monkeypatch.setenv('FINAL_REGISTRATION_ENABLED', '0')
    monkeypatch.setenv('FINAL_REGISTRATION_DISABLE_WORKER', '0')
    original = FinalRegistration.purge_expired
    def purge_expired_at_synthetic_cutoff(service):
        service.clock = lambda: RETENTION_TIMESTAMP + 1
        return original(service)
    monkeypatch.setattr(FinalRegistration, 'purge_expired', purge_expired_at_synthetic_cutoff)
    service = init_final_registration(Flask('disabled-maintenance'), None, harness.connection, False)
    try:
        assert service.thread is not None and service.thread.is_alive()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with harness.connection() as connection:
                remaining = connection.execute('SELECT COUNT(*) FROM final_passports').fetchone()[0]
            if not remaining:
                break
            time.sleep(.02)
        assert remaining == 0
        assert not service.enabled
    finally:
        service.stop()
