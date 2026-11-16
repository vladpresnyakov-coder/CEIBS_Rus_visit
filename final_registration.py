"""Private final registration, encrypted persistence and durable Telegram delivery.

Only init_final_registration performs schema/worker initialization. Connection
factories must be transactional context managers, like server.py's factories.
The returned service exposes run_once(), purge_expired() and stop(). Telegram
has no idempotency key: a crash after acceptance but before progress commit can
repeat the in-flight attachment; already committed progress is never repeated.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
import warnings
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import PurePath

import requests
from cryptography.fernet import Fernet
from flask import Blueprint, jsonify, request
from openpyxl import Workbook
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
FORMATS = ["image/jpeg", "image/png", "application/pdf"]
RETENTION_DATE = "2027-03-02"
RETENTION_TIMESTAMP = datetime(2027, 3, 2, tzinfo=timezone.utc).timestamp()
DRAFT_SECONDS = 24 * 3600
LEASE_SECONDS = 180
LANGUAGES = ("ru", "en", "zh")


class Rejected(Exception):
    def __init__(self, code="validation", status=400):
        self.code, self.status = code, status


class DeliveryFailure(Exception):
    def __init__(self, retry_after=0):
        # Do not store Telegram response bodies, URLs containing tokens, or PII.
        self.retry_after = retry_after


class TelegramTransport:
    def __init__(self, token):
        self._token = token

    def send_document(self, recipient, filename, content, mime, caption):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self._token}/sendDocument",
                data={"chat_id": str(recipient), "caption": caption,
                      "protect_content": "false", "disable_content_type_detection": "true"},
                files={"document": (filename, content, mime)},
                timeout=(10, 60), allow_redirects=False,
            )
            result = response.json()
            if response.status_code != 200 or not isinstance(result, dict) or result.get("ok") is not True:
                delay = result.get("parameters", {}).get("retry_after", 0) if isinstance(result, dict) else 0
                raise DeliveryFailure(delay if type(delay) is int and delay > 0 else 0)
        except DeliveryFailure:
            raise
        except Exception:
            raise DeliveryFailure() from None


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _uuid(value):
    if not isinstance(value, str):
        raise Rejected()
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise Rejected() from None
    return value


def _text(value, minimum=1, maximum=300):
    # Validate without normalizing passport spelling, whitespace or Unicode.
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or not value.strip():
        raise Rejected()
    if any(not (c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF
                or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
           for c in value):
        raise Rejected()
    return value


def validate_submission(data):
    if not isinstance(data, dict) or data.get("lang") not in LANGUAGES:
        raise Rejected()
    if data.get("privacyConsent") is not True:
        raise Rejected()
    people = data.get("people")
    if not isinstance(people, list) or not people:
        raise Rejected()
    clean_people = []
    for person in people:
        if not isinstance(person, dict):
            raise Rejected()
        clean_people.append({"fullName": _text(person.get("fullName"), 2),
                             "passportId": _uuid(person.get("passportId"))})
    if len({p["passportId"] for p in clean_people}) != len(people):
        raise Rejected()
    if len(people) == 1:
        if type(data.get("singleRoom")) is not bool:
            raise Rejected()
    elif data.get("singleRoom") is not None:
        raise Rejected()
    if data.get("paymentMethod") not in ("alipay", "international_transfer"):
        raise Rejected()
    clean = {"lang": data["lang"], "people": clean_people, "privacyConsent": True,
             "singleRoom": data.get("singleRoom"), "paymentMethod": data["paymentMethod"]}
    for field in ("arrival", "departure"):
        trip = data.get(field)
        if not isinstance(trip, dict):
            raise Rejected()
        city, day, hour, flight = (_text(trip.get(k)) for k in ("city", "date", "time", "flight"))
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not re.fullmatch(r"\d{2}:\d{2}", hour):
                raise ValueError()
            date.fromisoformat(day)
            datetime.strptime(hour, "%H:%M")
        except ValueError:
            raise Rejected() from None
        clean[field] = {"city": city, "date": day, "time": hour, "flight": flight}
    for field in ("phone", "wechat"):
        clean[field] = _text(data.get(field))
    return clean


def _safe_document(raw, filename, mime):
    suffix = PurePath(filename or "").suffix.lower()
    expected = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise Rejected("file_size", 413 if raw else 400)
    if expected.get(suffix) != mime or mime not in FORMATS:
        raise Rejected("file_type")
    output = io.BytesIO()
    try:
        if mime != "application/pdf":
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as check:
                    if check.format != ("JPEG" if mime == "image/jpeg" else "PNG"):
                        raise ValueError()
                    check.verify()
                with Image.open(io.BytesIO(raw)) as source:
                    source.load()
                    image = ImageOps.exif_transpose(source)
                    # A fresh image removes EXIF, comments, text, profiles and animation.
                    mode = "RGBA" if mime == "image/png" and "A" in image.getbands() else "RGB"
                    image = image.convert(mode)
                    clean = Image.new(mode, image.size)
                    clean.paste(image)
                    clean.save(output, format="PNG" if mime == "image/png" else "JPEG",
                               **({} if mime == "image/png" else {"quality": 95, "subsampling": 0}))
            extension = ".png" if mime == "image/png" else ".jpg"
        else:
            if not raw.startswith(b"%PDF-"):
                raise ValueError()
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError()
            # Inspect every xref object, including unused objects and encoded names,
            # not merely a byte substring (compressed JavaScript is still rejected).
            forbidden = {"/JS", "/JavaScript", "/AA", "/OpenAction", "/EmbeddedFiles",
                         "/EmbeddedFile", "/EF", "/Launch", "/RichMedia", "/XFA",
                         "/SubmitForm", "/ImportData", "/GoToR", "/URI", "/AcroForm"}
            forbidden_actions = {"/JavaScript", "/Launch", "/URI", "/GoToR", "/GoToE", "/SubmitForm",
                                 "/ResetForm", "/ImportData", "/Rendition", "/Movie", "/Sound", "/Hide",
                                 "/SetOCGState", "/Trans", "/GoTo3DView", "/Thread", "/Named"}
            seen = set()
            def inspect(obj):
                if isinstance(obj, IndirectObject):
                    ref = (obj.idnum, obj.generation)
                    if ref in seen:
                        return
                    seen.add(ref)
                    inspect(obj.get_object())
                elif isinstance(obj, DictionaryObject):
                    if forbidden.intersection(str(key) for key in obj):
                        raise ValueError()
                    for key, value in obj.items():
                        if str(key) == "/S" and str(value) in forbidden_actions:
                            raise ValueError()
                        if isinstance(value, str) and value in forbidden:
                            raise ValueError()
                        inspect(value)
                elif isinstance(obj, ArrayObject):
                    for value in obj:
                        inspect(value)
            inspect(reader.trailer)
            for generation, objects in reader.xref.items():
                if generation == 65535:
                    continue
                for number in objects:
                    if number:
                        inspect(IndirectObject(number, generation, reader))
            for number in reader.xref_objStm:
                inspect(IndirectObject(number, 0, reader))
            # Rebuild pages to discard orphan objects and document metadata.
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.add_metadata({})
            writer.write(output)
            extension = ".pdf"
    except Rejected:
        raise
    except Exception:
        raise Rejected("invalid_document") from None
    content = output.getvalue()
    if len(content) > MAX_FILE_BYTES:
        raise Rejected("file_size", 413)
    return content, {"mime": mime, "extension": extension}


class FinalRegistration:
    def __init__(self, app, pg_conn, sqlite_conn, is_postgres):
        self.app = app
        self.is_postgres = bool(is_postgres() if callable(is_postgres) else is_postgres)
        self.connection = pg_conn if self.is_postgres else sqlite_conn
        self.clock = time.time
        self._stop = threading.Event()
        self.thread = None
        self.opt_in = os.environ.get("FINAL_REGISTRATION_ENABLED") == "1"
        self.review_mode = os.environ.get("FINAL_REGISTRATION_REVIEW_MODE") == "1"
        self.review_token = os.environ.get("FINAL_REGISTRATION_REVIEW_TOKEN", "")
        self.cipher = None
        self.recipients = []
        self._key = b""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        minimum_recipients = 1 if os.environ.get("FINAL_REGISTRATION_ALLOW_SINGLE_RECIPIENT") == "1" else 2
        try:
            self._key = os.environ.get("FINAL_REGISTRATION_ENCRYPTION_KEY", "").encode("ascii")
            self.cipher = Fernet(self._key)
            recipients = json.loads(os.environ.get("FINAL_REGISTRATION_TELEGRAM_CHAT_IDS", "[]"))
            if (not isinstance(recipients, list)
                    or (len(recipients) != 1 if self.review_mode else len(recipients) < minimum_recipients)
                    or any(type(v) is not int or v <= 0 for v in recipients)
                    or len(set(recipients)) != len(recipients)):
                raise ValueError()
            self.recipients = recipients
        except Exception:
            self.recipients = []
        self.transport = TelegramTransport(token)
        self.configured = bool(self.cipher and self.recipients and token
                               and (not self.review_mode or len(self.review_token) >= 32))
        self._ensure_schema()

    @property
    def enabled(self):
        return self.opt_in and self.configured and self.clock() < RETENTION_TIMESTAMP

    @contextmanager
    def db(self, write=False):
        with self.connection() as conn:
            if write and not self.is_postgres:
                conn.execute("BEGIN IMMEDIATE")
            yield conn

    def sql(self, conn, query, values=()):
        return conn.execute(query.replace("?", "%s") if self.is_postgres else query, values)

    def _ensure_schema(self):
        blob = "BYTEA" if self.is_postgres else "BLOB"
        statements = [
            "CREATE TABLE IF NOT EXISTS final_drafts (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL, registration_id TEXT, submission_hash TEXT)",
            f"CREATE TABLE IF NOT EXISTS final_passports (id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, content {blob} NOT NULL, metadata {blob} NOT NULL, expires DOUBLE PRECISION NOT NULL)",
            f"CREATE TABLE IF NOT EXISTS final_registrations (id TEXT PRIMARY KEY, draft_id TEXT NOT NULL UNIQUE, metadata {blob} NOT NULL, workbook {blob}, created DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL)",
            f"CREATE TABLE IF NOT EXISTS final_outbox (id TEXT PRIMARY KEY, registration_id TEXT NOT NULL, recipient_hash TEXT NOT NULL, state {blob} NOT NULL, position INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, available DOUBLE PRECISION NOT NULL, lease_until DOUBLE PRECISION NOT NULL DEFAULT 0, lease_owner TEXT, done INTEGER NOT NULL DEFAULT 0, UNIQUE(registration_id, recipient_hash))",
            "CREATE INDEX IF NOT EXISTS final_passports_draft ON final_passports(draft_id)",
            "CREATE INDEX IF NOT EXISTS final_outbox_ready ON final_outbox(done, available, lease_until)",
        ]
        with self.db(write=True) as conn:
            for statement in statements:
                self.sql(conn, statement)

    def encrypt(self, value):
        return self.cipher.encrypt(_canonical(value))

    def decrypt(self, value):
        return json.loads(self.cipher.decrypt(bytes(value)))

    def digest(self, value):
        return hmac.new(self._key, value, hashlib.sha256).hexdigest()

    def authenticate(self, conn, draft_id, token, lock=False):
        _uuid(draft_id)
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise Rejected("unauthorized", 401)
        query = "SELECT token_hash, expires, registration_id, submission_hash FROM final_drafts WHERE id=?"
        if lock and self.is_postgres:
            query += " FOR UPDATE"
        row = self.sql(conn, query, (draft_id,)).fetchone()
        actual = hashlib.sha256(token.encode()).hexdigest()
        if not row or not hmac.compare_digest(row[0], actual):
            raise Rejected("unauthorized", 401)
        if row[1] <= self.clock() or self.clock() >= RETENTION_TIMESTAMP:
            raise Rejected("expired", 410)
        return row

    def create_draft(self, data):
        if not isinstance(data, dict) or data.get("lang") not in LANGUAGES:
            raise Rejected()
        draft_id, token = str(uuid.uuid4()), secrets.token_urlsafe(48)
        with self.db(write=True) as conn:
            # Check again after waiting for a database write lock, not only in
            # the HTTP hook: intake must close even across the cutoff instant.
            if not self.enabled:
                raise Rejected("unavailable", 503)
            now = self.clock()
            self.sql(conn, "INSERT INTO final_drafts(id,token_hash,created,expires) VALUES(?,?,?,?)",
                     (draft_id, hashlib.sha256(token.encode()).hexdigest(), now, min(now + DRAFT_SECONDS, RETENTION_TIMESTAMP)))
        return {"ok": True, "draftId": draft_id, "token": token}

    def upload(self, draft_id, token, file):
        # Check capability before parsing/decompressing attacker-controlled files.
        with self.db() as conn:
            row = self.authenticate(conn, draft_id, token)
            if row[2]:
                raise Rejected("already_submitted", 409)
        content, metadata = _safe_document(file.stream.read(MAX_FILE_BYTES + 1), file.filename, file.mimetype)
        passport_id = str(uuid.uuid4())
        with self.db(write=True) as conn:
            row = self.authenticate(conn, draft_id, token, lock=True)
            if row[2]:
                raise Rejected("already_submitted", 409)
            self.sql(conn, "INSERT INTO final_passports(id,draft_id,content,metadata,expires) VALUES(?,?,?,?,?)",
                     (passport_id, draft_id, self.cipher.encrypt(content), self.encrypt(metadata), row[1]))
        return {"ok": True, "passportId": passport_id}

    def submit(self, draft_id, token, data):
        clean = validate_submission(data)
        if self.review_mode:
            clean["reviewMode"] = True
        signature = self.digest(_canonical(clean))
        now = self.clock()
        with self.db(write=True) as conn:
            row = self.authenticate(conn, draft_id, token, lock=True)
            if row[2]:
                if not hmac.compare_digest(row[3], signature):
                    raise Rejected("already_submitted", 409)
                return {"ok": True, "registrationId": row[2], "participantsCount": len(clean["people"]), "notificationStatus": "queued"}
            # No SQL IN list/parameter or multipart count ceiling for companions.
            owned = {r[0] for r in self.sql(conn, "SELECT id FROM final_passports WHERE draft_id=? AND expires>?", (draft_id, now)).fetchall()}
            if any(p["passportId"] not in owned for p in clean["people"]):
                raise Rejected("passport_ownership")
            registration_id = str(uuid.uuid4())
            self.sql(conn, "INSERT INTO final_registrations(id,draft_id,metadata,created,expires) VALUES(?,?,?,?,?)",
                     (registration_id, draft_id, self.encrypt(clean), now, RETENTION_TIMESTAMP))
            self.sql(conn, "UPDATE final_drafts SET registration_id=?,submission_hash=?,expires=? WHERE id=?",
                     (registration_id, signature, RETENTION_TIMESTAMP, draft_id))
            used = {p["passportId"] for p in clean["people"]}
            for passport_id in owned:
                if passport_id in used:
                    self.sql(conn, "UPDATE final_passports SET expires=? WHERE id=?", (RETENTION_TIMESTAMP, passport_id))
                else:
                    self.sql(conn, "DELETE FROM final_passports WHERE id=?", (passport_id,))
            for recipient in self.recipients:
                self.sql(conn, "INSERT INTO final_outbox(id,registration_id,recipient_hash,state,available) VALUES(?,?,?,?,?)",
                         (str(uuid.uuid4()), registration_id, self.digest(str(recipient).encode()), self.encrypt({"recipient": recipient}), now))
        return {"ok": True, "registrationId": registration_id, "participantsCount": len(clean["people"]), "notificationStatus": "queued"}

    def purge_expired(self):
        now = self.clock()
        with self.db(write=True) as conn:
            self.sql(conn, "DELETE FROM final_outbox WHERE registration_id IN (SELECT id FROM final_registrations WHERE expires<=?)", (now,))
            self.sql(conn, "DELETE FROM final_outbox WHERE done=1 AND recipient_hash LIKE ? AND available<=?", ("manual-export:%", now))
            for table in ("final_passports", "final_drafts", "final_registrations"):
                self.sql(conn, f"DELETE FROM {table} WHERE expires<=?", (now,))

    def claim(self):
        now, owner = self.clock(), secrets.token_hex(24)
        with self.db(write=True) as conn:
            query = "SELECT id,registration_id,state,position,attempts FROM final_outbox WHERE done=0 AND available<=? AND lease_until<=? ORDER BY available,id LIMIT 1"
            if self.is_postgres:
                query += " FOR UPDATE SKIP LOCKED"
            row = self.sql(conn, query, (now, now)).fetchone()
            if row is None:
                return None
            self.sql(conn, "UPDATE final_outbox SET lease_owner=?,lease_until=? WHERE id=?", (owner, now + LEASE_SECONDS, row[0]))
        return (*row, owner)

    def workbook(self, conn, registration_id):
        query = "SELECT workbook FROM final_registrations WHERE id=? AND expires>?"
        if self.is_postgres:
            query += " FOR UPDATE"
        current = self.sql(conn, query, (registration_id, self.clock())).fetchone()
        if current is None:
            return None
        if current[0] is not None:
            return self.cipher.decrypt(bytes(current[0]))
        book = Workbook()
        sheet = book.active
        sheet.title = "Final registrations"
        columns = ["registrationId", "createdUTC", "personIndex", "role", "fullName", "passportId", "passportFilename", "lang",
                   "arrivalCity", "arrivalDate", "arrivalTime", "arrivalFlight", "departureCity", "departureDate", "departureTime", "departureFlight",
                   "singleRoom", "paymentMethod", "phone", "wechat", "privacyConsent"]
        sheet.append(columns)
        for reg_id, metadata, created in self.sql(conn, "SELECT id,metadata,created FROM final_registrations WHERE expires>? ORDER BY created,id", (self.clock(),)).fetchall():
            data = self.decrypt(metadata)
            if bool(data.get("reviewMode")) != self.review_mode:
                continue
            for index, person in enumerate(data["people"], 1):
                meta = self.sql(conn, "SELECT metadata FROM final_passports WHERE id=?", (person["passportId"],)).fetchone()
                extension = self.decrypt(meta[0])["extension"] if meta else ""
                values = [reg_id, datetime.fromtimestamp(created, timezone.utc).isoformat(), str(index), "primary" if index == 1 else "companion",
                          person["fullName"], person["passportId"], f"{reg_id}_{person['passportId']}{extension}", data["lang"]]
                for direction in ("arrival", "departure"):
                    values.extend(data[direction][k] for k in ("city", "date", "time", "flight"))
                values.extend(["" if data["singleRoom"] is None else str(data["singleRoom"]).lower(), data["paymentMethod"], data["phone"], data["wechat"], "true"])
                sheet.append(values)
                for cell in sheet[sheet.max_row]:
                    # Force literal strings including =,+,-,@ without changing spelling.
                    cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        buffer = io.BytesIO()
        book.save(buffer)
        content = buffer.getvalue()
        self.sql(conn, "UPDATE final_registrations SET workbook=? WHERE id=?", (self.cipher.encrypt(content), registration_id))
        return content

    def _attachment(self, registration_id, position):
        with self.db(write=True) as conn:
            row = self.sql(conn, "SELECT metadata FROM final_registrations WHERE id=? AND expires>?", (registration_id, self.clock())).fetchone()
            if not row:
                return None
            data = self.decrypt(row[0])
            if position == 0:
                return (f"final-registrations_{registration_id}.xlsx", self.workbook(conn, registration_id),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", len(data["people"]) + 1)
            if position > len(data["people"]):
                return None
            passport_id = data["people"][position - 1]["passportId"]
            passport = self.sql(conn, "SELECT content,metadata FROM final_passports WHERE id=? AND expires>?", (passport_id, self.clock())).fetchone()
            if not passport:
                return None
            meta = self.decrypt(passport[1])
            return (f"{registration_id}_{passport_id}{meta['extension']}", self.cipher.decrypt(bytes(passport[0])), meta["mime"], len(data["people"]) + 1)

    def run_once(self):
        """Purge and handle one recipient's complete job; return whether claimed."""
        self.purge_expired()
        if not self.enabled:
            return False
        job = self.claim()
        if not job:
            return False
        job_id, registration_id, encrypted_state, position, attempts, owner = job
        try:
            recipient = self.decrypt(encrypted_state)["recipient"]
            if recipient not in self.recipients:
                raise DeliveryFailure()
            while True:
                attachment = self._attachment(registration_id, position)
                if attachment is None or self.clock() >= RETENTION_TIMESTAMP:
                    # Expired data is not a successful delivery, and is not sent.
                    self.purge_expired()
                    return True
                filename, content, mime, total = attachment
                with self.db(write=True) as conn:
                    changed = self.sql(conn, "UPDATE final_outbox SET lease_until=? WHERE id=? AND lease_owner=? AND lease_until>? AND done=0",
                                       (self.clock() + LEASE_SECONDS, job_id, owner, self.clock())).rowcount
                if changed != 1:
                    return True
                self.transport.send_document(recipient, filename, content, mime, f"Final registration {registration_id}")
                position += 1
                with self.db(write=True) as conn:
                    changed = self.sql(conn, "UPDATE final_outbox SET position=?,done=?,lease_until=?,lease_owner=? WHERE id=? AND lease_owner=?",
                                       (position, int(position == total), 0 if position == total else self.clock() + LEASE_SECONDS,
                                        None if position == total else owner, job_id, owner)).rowcount
                if changed != 1 or position == total:
                    return True
        except Exception as exc:
            delay = exc.retry_after if isinstance(exc, DeliveryFailure) else 0
            # Honor Telegram's retry_after; generic exponential backoff is bounded.
            delay = max(delay, min(3600, 5 * (2 ** min(attempts, 10))))
            with self.db(write=True) as conn:
                self.sql(conn, "UPDATE final_outbox SET attempts=attempts+1,available=?,lease_until=0,lease_owner=NULL WHERE id=? AND lease_owner=?",
                         (self.clock() + delay, job_id, owner))
            return True

    def start(self):
        if self.thread is not None:
            return
        def loop():
            while not self._stop.is_set():
                try:
                    busy = self.run_once()
                except Exception:
                    # Deliberately do not log exception strings with tokens or PII.
                    busy = False
                if not busy:
                    self._stop.wait(5)
        self.thread = threading.Thread(target=loop, name="final-registration-maintenance", daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=2)


def init_final_registration(app, pg_conn, sqlite_conn, is_postgres):
    """Install isolated routes/storage and return the worker/maintenance service.

    Environment: FINAL_REGISTRATION_ENABLED=1, Fernet key in
    FINAL_REGISTRATION_ENCRYPTION_KEY, TELEGRAM_BOT_TOKEN and a JSON list of at
    least two distinct verified positive private chat IDs in
    FINAL_REGISTRATION_TELEGRAM_CHAT_IDS. No legacy recipient fallback.
    FINAL_REGISTRATION_DISABLE_WORKER=1 disables the maintenance/delivery thread.
    """
    # Parser diagnostics may quote malformed document fragments. This app has
    # no other PDF workflow; suppress library logs instead of exposing PII.
    logging.getLogger("pypdf").setLevel(logging.CRITICAL + 1)
    service = FinalRegistration(app, pg_conn, sqlite_conn, is_postgres)
    blueprint = Blueprint("final_registration", __name__, url_prefix="/api/final-register")
    previous_request_class = app.request_class

    class PrivateUploadRequest(previous_request_class):
        def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
            if self.path.startswith("/api/final-register/"):
                # Default Werkzeug streams spill plaintext to a temp file. Keep
                # these bounded private documents in RAM until encrypted in DB.
                return io.BytesIO()
            return super()._get_file_stream(total_content_length, content_type, filename, content_length)
    app.request_class = PrivateUploadRequest

    def review_authorized():
        return not service.review_mode or hmac.compare_digest(
            request.headers.get("X-Registration-Review", "").encode(), service.review_token.encode())

    @blueprint.before_request
    def readiness():
        if request.endpoint == "final_registration.config":
            return None
        if not service.enabled or not review_authorized():
            raise Rejected("unavailable", 503)
        if request.endpoint == "final_registration.passport":
            request.max_content_length = MAX_UPLOAD_BYTES
            request.max_form_parts = 2
            # Authenticate before Werkzeug parses or stores multipart bytes.
            with service.db() as conn:
                service.authenticate(conn, request.view_args["draft_id"], bearer())
        return None

    @blueprint.after_request
    def private_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.errorhandler(Rejected)
    def rejected(error):
        return jsonify(ok=False, error=error.code), error.status

    @blueprint.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(ok=False, error="file_size" if isinstance(error, RequestEntityTooLarge) else "invalid_request"), error.code

    @blueprint.errorhandler(Exception)
    def internal_error(error):
        return jsonify(ok=False, error="internal"), 500

    def bearer():
        header = request.headers.get("Authorization", "")
        return header[7:] if header.startswith("Bearer ") else ""

    @blueprint.get("/config")
    def config():
        data = dict(ok=True, enabled=service.enabled and review_authorized(), maxFileBytes=MAX_FILE_BYTES,
                    formats=FORMATS, retentionDate=RETENTION_DATE)
        if service.review_mode and review_authorized():
            data["reviewMode"] = True
        return jsonify(data)

    @blueprint.post("/drafts")
    def drafts():
        return jsonify(service.create_draft(request.get_json(silent=True)))

    @blueprint.post("/drafts/<draft_id>/passport")
    def passport(draft_id):
        files = request.files.getlist("file")
        if len(files) != 1 or set(request.files) != {"file"} or request.form:
            raise Rejected("file_required")
        return jsonify(service.upload(draft_id, bearer(), files[0]))

    @blueprint.post("/drafts/<draft_id>/submit")
    def submit(draft_id):
        return jsonify(service.submit(draft_id, bearer(), request.get_json(silent=True)))

    app.register_blueprint(blueprint)
    app.extensions["final_registration"] = service
    if os.environ.get("FINAL_REGISTRATION_DISABLE_WORKER") != "1":
        service.start()
    return service
