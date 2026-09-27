"""Export pre_registrations to .xlsx and deliver after each signup.

Preferred path: Telegram Bot API sendDocument when TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are set. Optional fallback: SMTP when SMTP_* is fully set.
Missing delivery config only logs a warning; callers must not fail the API.
"""

from __future__ import annotations

import io
import json
import logging
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openpyxl import Workbook

logger = logging.getLogger(__name__)

DEFAULT_MAIL_TO = "vlad.presnyakov@gmail.com"
XLSX_FILENAME = "pre_registrations.xlsx"
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Stable column order for the spreadsheet (matches DB schema).
EXPORT_COLUMNS: Sequence[str] = (
    "id",
    "full_name",
    "phone",
    "wechat",
    "cant",
    "join_choice",
    "join_label",
    "other_dates",
    "companies",
    "business_interest",
    "adults",
    "children",
    "child_ages",
    "tracks",
    "tracks_labels",
    "contact",
    "language",
    "user_agent",
    "created_at",
    "raw_json",
)


def _telegram_config() -> dict[str, str] | None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("TELEGRAM_CHAT_ID", chat_id),
        )
        if not value
    ]
    if missing:
        return None
    return {"token": token, "chat_id": chat_id}


def _smtp_config() -> dict[str, Any] | None:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    port_raw = (os.environ.get("SMTP_PORT") or "587").strip()
    mail_to = (os.environ.get("MAIL_TO") or DEFAULT_MAIL_TO).strip()
    mail_from = (os.environ.get("MAIL_FROM") or "").strip() or user or mail_to

    missing = [
        name
        for name, value in (
            ("SMTP_HOST", host),
            ("SMTP_USER", user),
            ("SMTP_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        return None

    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("Invalid SMTP_PORT %r; skipping email fallback", port_raw)
        return None

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "mail_to": mail_to,
        "mail_from": mail_from,
    }


def _cell_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def build_xlsx(rows: Sequence[dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "pre_registrations"
    ws.append(list(EXPORT_COLUMNS))
    for row in rows:
        ws.append([_cell_value(row.get(col)) for col in EXPORT_COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fetch_all_rows(fetch_fn: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return fetch_fn()


def _display_name(full_name: str) -> str:
    return (full_name or "").strip() or "(без имени)"


def _telegram_caption(name: str) -> str:
    return f"Новая предрегистрация: {name}\nполная таблица во вложении"


def _multipart_body(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    content_type: str,
) -> tuple[bytes, str]:
    boundary = f"----ceibs{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _send_telegram_document(
    *,
    token: str,
    chat_id: str,
    xlsx_bytes: bytes,
    caption: str,
) -> None:
    body, content_type = _multipart_body(
        {"chat_id": chat_id, "caption": caption},
        "document",
        XLSX_FILENAME,
        xlsx_bytes,
        XLSX_CONTENT_TYPE,
    )
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    req.add_header("Content-Length", str(len(body)))
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Telegram network error: {exc.reason}") from exc

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")


def _send_smtp_email(
    *,
    cfg: dict[str, Any],
    name: str,
    row_count: int,
    xlsx_bytes: bytes,
) -> None:
    subject = f"CEIBS Russia — новая предрегистрация: {name}"
    body = (
        "Новая предрегистрация сохранена в базе.\n\n"
        f"Имя: {name}\n"
        f"Всего записей в таблице: {row_count}\n\n"
        "Во вложении — полный экспорт таблицы pre_registrations (.xlsx)."
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["mail_from"]
    msg["To"] = cfg["mail_to"]
    msg.set_content(body)
    msg.add_attachment(
        xlsx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=XLSX_FILENAME,
    )

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(cfg["user"], cfg["password"])
        smtp.send_message(msg)


def send_pre_registration_export(
    *,
    full_name: str,
    fetch_fn: Callable[[], list[dict[str, Any]]],
) -> None:
    """Build full-table xlsx and deliver via Telegram (preferred) or SMTP.

    Never raises to the caller.
    """
    try:
        tg = _telegram_config()
        smtp = _smtp_config() if tg is None else None

        if tg is None and smtp is None:
            logger.warning(
                "No export delivery configured "
                "(set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, "
                "or SMTP_HOST + SMTP_USER + SMTP_PASSWORD); "
                "skipping pre-registration xlsx export"
            )
            return

        rows = fetch_all_rows(fetch_fn)
        xlsx_bytes = build_xlsx(rows)
        name = _display_name(full_name)

        if tg is not None:
            _send_telegram_document(
                token=tg["token"],
                chat_id=tg["chat_id"],
                xlsx_bytes=xlsx_bytes,
                caption=_telegram_caption(name),
            )
            logger.info(
                "Sent pre-registration export (%s rows) to Telegram chat %s",
                len(rows),
                tg["chat_id"],
            )
            return

        assert smtp is not None
        _send_smtp_email(
            cfg=smtp,
            name=name,
            row_count=len(rows),
            xlsx_bytes=xlsx_bytes,
        )
        logger.info(
            "Sent pre-registration export (%s rows) to %s",
            len(rows),
            smtp["mail_to"],
        )
    except Exception:
        logger.exception(
            "Failed to deliver pre-registration export; API still ok"
        )
