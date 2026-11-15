"""Synthetic documents only. Telegram transport is always replaced locally."""
import copy
import importlib
import io
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from flask import Flask
from openpyxl import load_workbook
from PIL import Image, PngImagePlugin
from pypdf import PdfReader, PdfWriter

from final_registration import (DeliveryFailure, MAX_FILE_BYTES, RETENTION_TIMESTAMP,
                                TelegramTransport, init_final_registration)


def test_backend_initializer_exists():
    assert callable(importlib.import_module("final_registration").init_final_registration)


def png():
    output = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "SYNTHETIC_PRIVATE_METADATA")
    Image.new("RGB", (32, 24), color="white").save(output, "PNG", pnginfo=info)
    return output.getvalue()


def pdf(active=False, encrypted=False, attachment=False):
    writer = PdfWriter()
    writer.add_blank_page(100, 150)
    if active:
        from pypdf.actions import JavaScript
        writer.add_open_action(JavaScript("app.alert('synthetic test')"))
    if encrypted:
        writer.encrypt("synthetic-not-a-secret")
    if attachment:
        writer.add_attachment("synthetic.txt", b"synthetic attachment")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setenv("FINAL_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("FINAL_REGISTRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[111111111,222222222]")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-not-a-real-token")
    monkeypatch.setenv("FINAL_REGISTRATION_DISABLE_WORKER", "1")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-99999999")
    path = tmp_path / "private.sqlite"
    @contextmanager
    def connection():
        conn = sqlite3.connect(path, timeout=15)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    with connection() as conn:
        conn.execute("CREATE TABLE pre_registrations (id INTEGER PRIMARY KEY, full_name TEXT)")
        conn.execute("INSERT INTO pre_registrations VALUES (1, 'synthetic legacy unchanged')")
    app = Flask(__name__, static_folder=None)
    app.testing = True
    service = init_final_registration(app, None, connection, lambda: False)
    service.clock = lambda: 1794700800.0  # synthetic fixed instant before retention
    sent = []
    service.transport.send_document = lambda *args: sent.append(args)
    return SimpleNamespace(app=app, client=app.test_client(), service=service,
                           connection=connection, sent=sent, path=path)


def draft(h, lang="en"):
    response = h.client.post("/api/final-register/drafts", json={"lang": lang})
    assert response.status_code == 200, response.json
    return response.json


def auth(d):
    return {"Authorization": "Bearer " + d["token"]}


def upload(h, d, content=None, filename="synthetic.png", mime="image/png"):
    return h.client.post(f"/api/final-register/drafts/{d['draftId']}/passport",
                         headers=auth(d), data={"file": (io.BytesIO(png() if content is None else content), filename, mime)})


def payload(passports, name="Synthetic Participant"):
    return {"lang": "en", "people": [{"fullName": name + (f" {i}" if i else ""), "passportId": p} for i, p in enumerate(passports)],
            "arrival": {"city": "Москва", "date": "2027-01-20", "time": "03:04", "flight": " CA 001 "},
            "departure": {"city": "上海", "date": "2027-02-04", "time": "23:45", "flight": "SU 202"},
            "singleRoom": False if len(passports) == 1 else None,
            "paymentMethod": "international_transfer", "privacyConsent": True,
            "phone": "+1 202 555 0123", "wechat": "SyntheticContact"}


def submit(h, d, data):
    return h.client.post(f"/api/final-register/drafts/{d['draftId']}/submit", headers=auth(d), json=data)


def group(h, count=1, name="Synthetic Participant"):
    d = draft(h)
    passports = []
    for _ in range(count):
        response = upload(h, d)
        assert response.status_code == 200, response.json
        passports.append(response.json["passportId"])
    data = payload(passports, name)
    response = submit(h, d, data)
    assert response.status_code == 200, response.json
    return d, data, response.json


def test_config_does_not_leak_and_private_endpoints_absent(harness):
    h = harness
    config = h.client.get("/api/final-register/config")
    assert config.json == {"ok": True, "enabled": True, "maxFileBytes": 10485760,
                           "formats": ["image/jpeg", "image/png", "application/pdf"], "retentionDate": "2027-03-02"}
    assert config.headers["Cache-Control"] == "no-store"
    d, data, result = group(h)
    for path in ["/api/final-register/export", "/api/final-register/registrations",
                 f"/api/final-register/passports/{data['people'][0]['passportId']}",
                 f"/api/final-register/{result['registrationId']}"]:
        assert h.client.get(path).status_code == 404
    assert h.client.get(f"/api/final-register/drafts/{d['draftId']}/passport").status_code == 405


@pytest.mark.parametrize("variable,value", [
    ("FINAL_REGISTRATION_ENCRYPTION_KEY", ""), ("FINAL_REGISTRATION_ENCRYPTION_KEY", "bad"),
    ("TELEGRAM_BOT_TOKEN", ""), ("FINAL_REGISTRATION_ENABLED", "0"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[]"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[111111111]"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[111111111,-222222222]"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[111111111,111111111]"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", '[111111111,"@OlgaSit"]'),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[true,222222222]"),
    ("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "not-json"),
])
def test_fail_closed(harness, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    app = Flask("closed", static_folder=None)
    service = init_final_registration(app, None, harness.connection, False)
    service.clock = harness.service.clock
    assert app.test_client().get("/api/final-register/config").json["enabled"] is False
    assert app.test_client().post("/api/final-register/drafts", json={"lang": "en"}).status_code == 503
    assert service.run_once() is False


@pytest.mark.parametrize("count", [1, 2, 25])
def test_one_two_unlimited_people_and_idempotency(harness, count):
    h = harness
    d, data, result = group(h, count)
    assert result["participantsCount"] == count
    assert result["notificationStatus"] == "queued"
    assert submit(h, d, data).json == result
    changed = copy.deepcopy(data)
    changed["arrival"]["city"] = "different"
    assert submit(h, d, changed).status_code == 409
    assert upload(h, d).status_code == 409
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_outbox").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM final_registrations").fetchone()[0] == 1
        assert conn.execute("SELECT full_name FROM pre_registrations").fetchone()[0] == "synthetic legacy unchanged"


@pytest.mark.parametrize("change", [
    lambda p: p.pop("privacyConsent"), lambda p: p.update(privacyConsent=False),
    lambda p: p.update(privacyConsent="true"), lambda p: p.update(paymentMethod="card"),
    lambda p: p.pop("paymentMethod"), lambda p: p.update(singleRoom=None),
    lambda p: p.update(singleRoom=1), lambda p: p.update(people=[]),
    lambda p: p["people"][0].update(fullName="A"), lambda p: p["people"][0].update(fullName="x" * 301),
    lambda p: p["people"][0].pop("passportId"), lambda p: p.update(lang="de"),
    lambda p: p["arrival"].update(date="2027-02-30"), lambda p: p["arrival"].update(time="24:00"),
    lambda p: p["departure"].update(time="3:04"), lambda p: p["departure"].pop("flight"),
    lambda p: p.pop("arrival"), lambda p: p.update(phone=[]),
])
def test_required_fields_and_conditional_single_room(harness, change):
    h = harness
    d = draft(h)
    passport = upload(h, d).json["passportId"]
    data = payload([passport])
    change(data)
    assert submit(h, d, data).status_code == 400
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_registrations").fetchone()[0] == 0


def test_multi_person_rejects_stale_single_room_and_duplicate_passports(harness):
    h = harness
    d = draft(h)
    ids = [upload(h, d).json["passportId"] for _ in range(2)]
    data = payload(ids)
    for value in [True, False, "false"]:
        data["singleRoom"] = value
        assert submit(h, d, data).status_code == 400
    data = payload([ids[0], ids[0]])
    assert submit(h, d, data).status_code == 400
    assert submit(h, d, payload(ids)).status_code == 200


def test_capabilities_ownership_and_no_plaintext_at_rest(harness):
    h = harness
    first, second = draft(h), draft(h)
    response = upload(h, first)
    passport_id = response.json["passportId"]
    assert submit(h, second, payload([passport_id])).status_code == 400
    url = f"/api/final-register/drafts/{first['draftId']}/passport"
    assert h.client.post(url, data={}).status_code == 401
    assert h.client.post(url, headers=auth(second), data={}).status_code == 401
    data = payload([passport_id], "精确拼写 =SYNTHETIC_PRIVATE_NAME")
    assert submit(h, first, data).status_code == 200
    with h.connection() as conn:
        row = conn.execute("SELECT content,metadata FROM final_passports").fetchone()
        original = h.service.cipher.decrypt(row[0])
        with Image.open(io.BytesIO(original)) as image:
            assert "Comment" not in image.info
        assert png() not in row[0]
        assert "image/png" not in str(row[1])
        persisted = b" ".join(str(row).encode() for table in ["final_drafts", "final_passports", "final_registrations", "final_outbox"]
                             for row in conn.execute(f"SELECT * FROM {table}"))
        for sensitive in [first["token"].encode(), second["token"].encode(), data["people"][0]["fullName"].encode(), b"CA 001", b"SYNTHETIC_PRIVATE_METADATA", b"111111111", b"222222222"]:
            assert sensitive not in persisted
    disk = h.path.read_bytes()
    assert first["token"].encode() not in disk
    assert b"SYNTHETIC_PRIVATE_NAME" not in disk


@pytest.mark.parametrize("content,filename,mime", [
    (b"<html>not a passport</html>", "scan.png", "image/png"),
    (b"<svg></svg>", "scan.svg", "image/svg+xml"),
    (b"%PDF-garbage", "scan.pdf", "application/pdf"),
    (png(), "scan.jpg", "image/jpeg"),
    (png(), "scan.png", "text/html"),
    (png(), "scan.html", "image/png"),
    (pdf(active=True), "scan.pdf", "application/pdf"),
    (pdf(encrypted=True), "scan.pdf", "application/pdf"),
    (pdf(attachment=True), "scan.pdf", "application/pdf"),
    (b"", "scan.png", "image/png"),
])
def test_reject_spoofed_active_encrypted_documents(harness, content, filename, mime):
    assert upload(harness, draft(harness), content, filename, mime).status_code == 400
    with harness.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_passports").fetchone()[0] == 0


def test_pdf_and_jpeg_content_and_unsafe_filename(harness):
    h = harness
    d = draft(h)
    assert upload(h, d, pdf(), "../../synthetic.pdf", "application/pdf").status_code == 200
    output = io.BytesIO()
    Image.new("RGB", (20, 20), color="white").save(output, "JPEG")
    assert upload(h, d, output.getvalue(), "scan.jpeg", "image/jpeg").status_code == 200
    with h.connection() as conn:
        rows = conn.execute("SELECT metadata,content FROM final_passports").fetchall()
        for metadata, content in rows:
            meta = h.service.decrypt(metadata)
            assert "filename" not in meta
            if meta["mime"] == "application/pdf":
                assert len(PdfReader(io.BytesIO(h.service.cipher.decrypt(content))).pages) == 1


def test_oversize_file_request_and_in_memory_stream(harness):
    h = harness
    d = draft(h)
    assert upload(h, d, b"x" * (MAX_FILE_BYTES + 1)).status_code == 413
    assert upload(h, d, b"x" * (13 * 1024 * 1024)).status_code == 413
    with h.app.test_request_context(f"/api/final-register/drafts/{d['draftId']}/passport"):
        from flask import request
        stream = request._get_file_stream(1024 * 1024, "image/png")
        assert isinstance(stream, io.BytesIO)
    assert h.app.config["MAX_FORM_PARTS"] == 1000  # no shared global change


def test_full_workbook_both_private_recipients_new_group_only_and_literals(harness):
    h = harness
    _, old_data, old = group(h)
    assert h.service.run_once() and h.service.run_once()
    h.sent.clear()
    _, new_data, new = group(h, 2, "=1+1")
    assert h.service.run_once() and h.service.run_once()
    assert not h.service.run_once()
    assert len(h.sent) == 6
    for recipient in (111111111, 222222222):
        sent = [call for call in h.sent if call[0] == recipient]
        assert len(sent) == 3
        assert sent[0][1].endswith(".xlsx")
        workbook = load_workbook(io.BytesIO(sent[0][2]), data_only=False)
        sheet = workbook.active
        rows = list(sheet.iter_rows())
        assert len(rows) == 4
        headers = [cell.value for cell in rows[0]]
        records = [dict(zip(headers, [cell.value for cell in row])) for row in rows[1:]]
        assert {r["registrationId"] for r in records} == {old["registrationId"], new["registrationId"]}
        formula_name = [row[headers.index("fullName")] for row in rows[1:] if row[headers.index("registrationId")].value == new["registrationId"]][0]
        assert formula_name.value == "=1+1" and formula_name.data_type == "s"
        assert all(r["arrivalFlight"] == " CA 001 " for r in records)
        for person in new_data["people"]:
            filename = f"{new['registrationId']}_{person['passportId']}.png"
            assert filename in [s[1] for s in sent[1:]]
            assert filename in [r["passportFilename"] for r in records]
        assert not any(old_data["people"][0]["passportId"] in s[1] for s in sent[1:])
    assert not any(call[0] < 0 for call in h.sent)


def test_durable_retry_preserves_per_file_progress_after_reinitialization(harness):
    h = harness
    group(h, 2)
    attempts = []
    def send(*args):
        attempts.append(args)
        if len(attempts) == 2:
            raise DeliveryFailure(45)
        h.sent.append(args)
    h.service.transport.send_document = send
    assert h.service.run_once()
    with h.connection() as conn:
        failed = conn.execute("SELECT position,attempts,available FROM final_outbox WHERE attempts=1").fetchone()
        assert failed == (1, 1, h.service.clock() + 45)
    other_app = Flask("restarted", static_folder=None)
    restarted = init_final_registration(other_app, None, h.connection, False)
    restarted.clock = lambda: h.service.clock() + 46
    restarted.transport.send_document = lambda *args: h.sent.append(args)
    assert restarted.run_once() and restarted.run_once()
    assert not restarted.run_once()
    assert len(h.sent) == 6
    for recipient in (111111111, 222222222):
        assert len([s for s in h.sent if s[0] == recipient and s[1].endswith(".xlsx")]) == 1
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_outbox WHERE done=1 AND position=3").fetchone()[0] == 2


def test_two_workers_cannot_claim_same_job_and_expired_lease_recoverable(harness):
    h = harness
    group(h)
    barrier = threading.Barrier(2)
    def claim():
        barrier.wait()
        return h.service.claim()
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: claim(), range(2)))
    assert jobs[0][0] != jobs[1][0]
    assert h.service.claim() is None
    now = h.service.clock()
    h.service.clock = lambda: now + 181
    assert h.service.claim() is not None


def test_concurrent_idempotent_submit_does_not_duplicate_outbox(harness):
    h = harness
    d = draft(h)
    data = payload([upload(h, d).json["passportId"]])
    def send(_):
        with h.app.test_client() as client:
            return client.post(f"/api/final-register/drafts/{d['draftId']}/submit", headers=auth(d), json=data)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(send, range(4)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json["registrationId"] for r in responses}) == 1
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_outbox").fetchone()[0] == 2


def test_orphan_cleanup_final_retention_and_no_expired_delivery(harness):
    h = harness
    orphan = draft(h)
    assert upload(h, orphan).status_code == 200
    group(h)
    now = h.service.clock()
    h.service.clock = lambda: now + 86401
    h.service.purge_expired()
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_drafts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM final_passports").fetchone()[0] == 1
    h.service.clock = lambda: RETENTION_TIMESTAMP
    assert not h.service.run_once()
    assert not h.sent
    assert not h.client.get("/api/final-register/config").json["enabled"]
    with h.connection() as conn:
        for table in ["final_drafts", "final_passports", "final_registrations", "final_outbox"]:
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM pre_registrations").fetchone()[0] == 1


def test_expired_capability_cannot_upload(harness):
    h = harness
    d = draft(h)
    now = h.service.clock()
    h.service.clock = lambda: now + 86401
    assert upload(h, d).status_code == 410


def test_plain_pdf_transparency_is_not_an_active_action(harness):
    from pypdf.generic import DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(100, 150)
    page[NameObject("/Group")] = DictionaryObject({NameObject("/S"): NameObject("/Transparency")})
    buffer = io.BytesIO()
    writer.write(buffer)
    response = upload(harness, draft(harness), buffer.getvalue(), "normal.pdf", "application/pdf")
    assert response.status_code == 200, response.json


@pytest.mark.parametrize("field,value", [("lang", []), ("paymentMethod", {}), ("lang", None)])
def test_invalid_enum_types_are_validation_not_server_errors(harness, field, value):
    d = draft(harness)
    data = payload([upload(harness, d).json["passportId"]])
    data[field] = value
    assert submit(harness, d, data).status_code == 400


def test_retention_cutoff_rejects_new_drafts_uploads_and_submit(harness):
    h = harness
    d = draft(h)
    data = payload([upload(h, d).json["passportId"]])
    h.service.clock = lambda: RETENTION_TIMESTAMP
    assert h.client.post("/api/final-register/drafts", json={"lang": "en"}).status_code == 503
    assert upload(h, d).status_code == 503
    assert submit(h, d, data).status_code == 503
    assert h.client.get("/api/final-register/config").json["enabled"] is False


def test_pdf_parser_diagnostics_cannot_leak_document_fragments(harness, caplog):
    import logging
    logging.getLogger("pypdf._reader").error("SYNTHETIC_PRIVATE_DOCUMENT_FRAGMENT")
    assert "SYNTHETIC_PRIVATE_DOCUMENT_FRAGMENT" not in caplog.text


def test_transaction_failure_never_reports_success_and_can_retry(harness):
    h = harness
    d = draft(h)
    data = payload([upload(h, d).json["passportId"]])
    with h.connection() as conn:
        conn.execute("CREATE TRIGGER fail_queue BEFORE INSERT ON final_outbox BEGIN SELECT RAISE(FAIL, 'SYNTHETIC_PRIVATE_DB_ERROR'); END")
    response = submit(h, d, data)
    assert response.status_code == 500
    assert response.json == {"ok": False, "error": "internal"}
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_registrations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM final_outbox").fetchone()[0] == 0
        assert conn.execute("SELECT registration_id FROM final_drafts").fetchone()[0] is None
        conn.execute("DROP TRIGGER fail_queue")
    assert submit(h, d, data).status_code == 200


def test_actual_background_worker_delivers_committed_jobs(harness):
    h = harness
    group(h, 2)
    delivered = threading.Event()
    def send(*args):
        h.sent.append(args)
        if len(h.sent) == 6:
            delivered.set()
    h.service.transport.send_document = send
    h.service.start()
    try:
        assert delivered.wait(10)
    finally:
        h.service.stop()
    assert not h.service.thread.is_alive()
    with h.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM final_outbox WHERE done=1").fetchone()[0] == 2


def test_actual_transport_http_boundary_and_429_no_real_network(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=429, json=lambda: {"ok": False, "parameters": {"retry_after": 33}})
    monkeypatch.setattr("final_registration.requests.post", post)
    transport = TelegramTransport("synthetic-token")
    with pytest.raises(DeliveryFailure) as error:
        transport.send_document(111111111, "synthetic.png", png(), "image/png", "Synthetic")
    assert error.value.retry_after == 33
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["data"]["chat_id"] == "111111111"
    assert calls[0][1]["files"]["document"][0] == "synthetic.png"
