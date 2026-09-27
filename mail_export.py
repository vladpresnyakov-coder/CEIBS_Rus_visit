"""Export pre_registrations to .xlsx and email the full table after each signup.

SMTP is optional: missing env vars only log a warning; callers must not fail
the API response if send fails.
"""

from __future__ import annotations

import io
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Sequence

from openpyxl import Workbook

logger = logging.getLogger(__name__)

DEFAULT_MAIL_TO = "vlad.presnyakov@gmail.com"

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
        logger.warning(
            "SMTP not configured (%s missing); skipping pre-registration email",
            ", ".join(missing),
        )
        return None

    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("Invalid SMTP_PORT %r; skipping pre-registration email", port_raw)
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
        import json

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


def send_pre_registration_export(
    *,
    full_name: str,
    fetch_fn: Callable[[], list[dict[str, Any]]],
) -> None:
    """Build full-table xlsx and email it. Never raises to the caller."""
    try:
        cfg = _smtp_config()
        if cfg is None:
            return

        rows = fetch_all_rows(fetch_fn)
        xlsx_bytes = build_xlsx(rows)
        name = (full_name or "").strip() or "(без имени)"
        subject = f"CEIBS Russia — новая предрегистрация: {name}"
        body = (
            "Новая предрегистрация сохранена в базе.\n\n"
            f"Имя: {name}\n"
            f"Всего записей в таблице: {len(rows)}\n\n"
            "Во вложении — полный экспорт таблицы pre_registrations (.xlsx)."
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["mail_from"]
        msg["To"] = cfg["mail_to"]
        msg.set_content(body)
        filename = "pre_registrations.xlsx"
        msg.add_attachment(
            xlsx_bytes,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )

        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)

        logger.info(
            "Sent pre-registration export (%s rows) to %s",
            len(rows),
            cfg["mail_to"],
        )
    except Exception:
        logger.exception("Failed to email pre-registration export; API still ok")
