"""Environment-triggered private snapshot delivery; no public administrative route."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import threading
import uuid
from datetime import datetime, timezone

import requests
from openpyxl import Workbook

from final_registration import RETENTION_TIMESTAMP


def _verified_document(token, recipient, filename, content, mime, caption):
    try:
        root = 'https://api.telegram.org/bot' + token
        response = requests.post(root + '/sendDocument', data={
            'chat_id': str(recipient), 'caption': caption, 'protect_content': 'false',
            'disable_content_type_detection': 'true'},
            files={'document': (filename, content, mime)}, timeout=(10, 90), allow_redirects=False)
        result = response.json()
        if response.status_code != 200 or result.get('ok') is not True:
            raise ValueError()
        message = result['result']
        if message['chat']['id'] != recipient or message['chat']['type'] != 'private':
            raise ValueError()
        file_id = message['document']['file_id']
        info = requests.get(root + '/getFile', params={'file_id': file_id}, timeout=(10, 30), allow_redirects=False).json()
        if info.get('ok') is not True:
            raise ValueError()
        path = info['result']['file_path']
        if not isinstance(path, str) or path.startswith('/') or '..' in path or '://' in path:
            raise ValueError()
        downloaded = requests.get('https://api.telegram.org/file/bot' + token + '/' + path,
                                  timeout=(10, 90), allow_redirects=False)
        digest = hashlib.sha256(content).hexdigest()
        if downloaded.status_code != 200 or hashlib.sha256(downloaded.content).hexdigest() != digest:
            raise ValueError()
        return {'message_id': message['message_id'], 'file_id': file_id, 'sha256': digest}
    except Exception:
        raise RuntimeError('private document delivery or read-back failed') from None


def _snapshot(service, conn, recipient):
    book = Workbook()
    main = book.active
    assert main is not None
    main.title = 'Final registrations'
    headings = ['registrationId', 'createdUTC', 'personIndex', 'role', 'fullName', 'passportId',
                'passportFilename', 'lang', 'arrivalCity', 'arrivalDate', 'arrivalTime', 'arrivalFlight',
                'departureCity', 'departureDate', 'departureTime', 'departureFlight', 'singleRoom',
                'paymentMethod', 'phone', 'wechat', 'privacyConsent']
    main.append(headings)
    review = None
    files = []
    counts = {'finalRegistrations': 0, 'testRegistrations': 0, 'participants': 0}
    now = service.clock()
    rows = service.sql(conn, 'SELECT id,metadata,created FROM final_registrations WHERE expires>? ORDER BY created,id', (now,)).fetchall()
    for reg_id, metadata, created in rows:
        data = service.decrypt(metadata)
        is_review = bool(data.get('reviewMode'))
        counts['testRegistrations' if is_review else 'finalRegistrations'] += 1
        if is_review and review is None:
            review = book.create_sheet('Test registrations')
            review.append(headings)
        sheet = review if is_review else main
        assert sheet is not None
        for index, person in enumerate(data['people'], 1):
            row = service.sql(conn, 'SELECT metadata FROM final_passports WHERE id=? AND expires>?',
                              (person['passportId'], now)).fetchone()
            if row is None:
                raise RuntimeError('submitted passport is unavailable')
            meta = service.decrypt(row[0])
            filename = reg_id + '_' + person['passportId'] + meta['extension']
            files.append({'passportId': person['passportId'], 'filename': filename, 'mime': meta['mime']})
            values = [reg_id, datetime.fromtimestamp(created, timezone.utc).isoformat(), str(index),
                      'primary' if index == 1 else 'companion', person['fullName'], person['passportId'],
                      filename, data['lang']]
            for direction in ('arrival', 'departure'):
                values.extend(data[direction][key] for key in ('city', 'date', 'time', 'flight'))
            values.extend(['' if data['singleRoom'] is None else str(data['singleRoom']).lower(),
                           data['paymentMethod'], data.get('phone', ''), data.get('wechat', ''), 'true'])
            sheet.append(values)
            for cell in sheet[sheet.max_row]:
                cell.data_type = 's'
            counts['participants'] += 1
    for sheet in book:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    book.save(output)
    return {'kind': 'manual_snapshot', 'recipient': recipient, 'counts': counts, 'receipts': [],
            'files': [{'filename': 'CEIBS-final-registrations.xlsx',
                       'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       'content': base64.b64encode(output.getvalue()).decode()}] + files}


def dispatch_snapshot(service, request_id, recipient, send=None):
    if (type(recipient) is not int or recipient not in service.recipients or not service.enabled
            or str(uuid.UUID(request_id)) != request_id):
        raise ValueError('invalid private snapshot request')
    job_id = request_id
    with service.db(write=True) as conn:
        existing = service.sql(conn, 'SELECT state FROM final_outbox WHERE id=?', (job_id,)).fetchone()
        if existing is None:
            state = _snapshot(service, conn, recipient)
            service.sql(conn, 'INSERT INTO final_outbox(id,registration_id,recipient_hash,state,available,done) VALUES(?,?,?,?,?,1) ON CONFLICT(id) DO NOTHING',
                        (job_id, 'manual_snapshot', 'manual-export:' + request_id,
                         service.encrypt(state), RETENTION_TIMESTAMP))
    deliver = send or (lambda *args: _verified_document(os.environ['TELEGRAM_BOT_TOKEN'], *args))
    while True:
        with service.db(write=True) as conn:
            query = 'SELECT state,position FROM final_outbox WHERE id=?'
            if service.is_postgres:
                query += ' FOR UPDATE'
            row = service.sql(conn, query, (job_id,)).fetchone()
            if row is None:
                raise RuntimeError('snapshot expired')
            state, position = service.decrypt(row[0]), row[1]
            if state.get('kind') != 'manual_snapshot' or state['recipient'] != recipient:
                raise ValueError('snapshot ownership mismatch')
            if position == len(state['files']):
                return {'requestId': request_id, 'recipient': recipient, 'files': position,
                        'passports': len(state['files']) - 1, 'verified': len(state['receipts']),
                        'messageIds': [entry['message_id'] for entry in state['receipts']], **state['counts']}
            if service.clock() >= RETENTION_TIMESTAMP:
                raise RuntimeError('snapshot expired')
            item = state['files'][position]
            if 'content' in item:
                content = base64.b64decode(item['content'])
                caption = 'CEIBS: current registrations. Test registrations, if any, are on a separate sheet.'
            else:
                passport = service.sql(conn, 'SELECT content FROM final_passports WHERE id=? AND expires>?',
                                       (item['passportId'], service.clock())).fetchone()
                if passport is None:
                    raise RuntimeError('snapshot passport expired')
                content = service.cipher.decrypt(bytes(passport[0]))
                caption = 'CEIBS passport scan ' + str(position) + '/' + str(len(state['files']) - 1)
            receipt = deliver(recipient, item['filename'], content, item['mime'], caption)
            state['receipts'].append(receipt)
            service.sql(conn, 'UPDATE final_outbox SET state=?,position=? WHERE id=?',
                        (service.encrypt(state), position + 1, job_id))


def start_environment_snapshot(service):
    request_id = os.environ.get('FINAL_REGISTRATION_EXPORT_REQUEST_ID', '')
    if not request_id:
        return
    def run():
        try:
            recipient = int(os.environ['FINAL_REGISTRATION_EXPORT_RECIPIENT'])
            result = dispatch_snapshot(service, request_id, recipient)
            print('CEIBS_EXPORT_RECEIPT ' + json.dumps(result, separators=(',', ':')), flush=True)
        except Exception as exc:
            print('CEIBS_EXPORT_ERROR ' + json.dumps({'requestId': request_id, 'errorType': type(exc).__name__}), flush=True)
    threading.Thread(target=run, name='private-registration-snapshot', daemon=True).start()
