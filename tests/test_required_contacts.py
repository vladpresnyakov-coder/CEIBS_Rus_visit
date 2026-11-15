"""Required primary contact details must be enforced before storage."""
import pytest
from test_final_registration import harness, draft, upload, payload, submit


@pytest.mark.parametrize('field', ['phone', 'wechat'])
@pytest.mark.parametrize('value', [None, '', '   '])
def test_missing_or_blank_contact_is_rejected(harness, field, value):
    d = draft(harness)
    data = payload([upload(harness, d).json['passportId']])
    data.update(phone='+1 202 555 0123', wechat='SyntheticContact')
    if value is None:
        data.pop(field)
    else:
        data[field] = value
    assert submit(harness, d, data).status_code == 400
    with harness.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM final_registrations').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM final_outbox').fetchone()[0] == 0
