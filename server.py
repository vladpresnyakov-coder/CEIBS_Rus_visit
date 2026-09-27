#!/usr/bin/env python3
"""Serve the static site and persist pre-registrations.

Uses PostgreSQL when DATABASE_URL is set (Railway), otherwise SQLite at
data/pre_registrations.sqlite for local runs.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SQLITE_PATH = DATA_DIR / "pre_registrations.sqlite"
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()

app = Flask(__name__, static_folder=None)


def _is_postgres() -> bool:
    return bool(DATABASE_URL)


@contextmanager
def _pg_conn():
    import psycopg

    # Railway sometimes provides postgres://; psycopg expects postgresql://
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    conn = psycopg.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _sqlite_conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


PG_DDL = """
CREATE TABLE IF NOT EXISTS pre_registrations (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    wechat TEXT NOT NULL DEFAULT '',
    cant BOOLEAN NOT NULL DEFAULT FALSE,
    join_choice TEXT NOT NULL DEFAULT '',
    join_label TEXT NOT NULL DEFAULT '',
    other_dates TEXT NOT NULL DEFAULT '',
    companies TEXT NOT NULL DEFAULT '',
    business_interest TEXT NOT NULL DEFAULT '',
    adults TEXT NOT NULL DEFAULT '',
    children TEXT NOT NULL DEFAULT '',
    child_ages TEXT NOT NULL DEFAULT '',
    tracks TEXT NOT NULL DEFAULT '',
    tracks_labels TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_json JSONB
)
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS pre_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    wechat TEXT NOT NULL DEFAULT '',
    cant INTEGER NOT NULL DEFAULT 0,
    join_choice TEXT NOT NULL DEFAULT '',
    join_label TEXT NOT NULL DEFAULT '',
    other_dates TEXT NOT NULL DEFAULT '',
    companies TEXT NOT NULL DEFAULT '',
    business_interest TEXT NOT NULL DEFAULT '',
    adults TEXT NOT NULL DEFAULT '',
    children TEXT NOT NULL DEFAULT '',
    child_ages TEXT NOT NULL DEFAULT '',
    tracks TEXT NOT NULL DEFAULT '',
    tracks_labels TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    raw_json TEXT
)
"""


def ensure_schema() -> None:
    if _is_postgres():
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(PG_DDL)
    else:
        with _sqlite_conn() as conn:
            conn.execute(SQLITE_DDL)


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def insert_registration(payload: dict, user_agent: str) -> None:
    join_choice = _text(payload.get("join"))
    cant = join_choice == "cant"
    row = {
        "full_name": _text(payload.get("fullName")),
        "phone": _text(payload.get("phone")),
        "wechat": _text(payload.get("wechat")),
        "cant": cant,
        "join_choice": join_choice,
        "join_label": _text(payload.get("joinLabel")),
        "other_dates": _text(payload.get("otherDates")),
        "companies": _text(payload.get("companies")),
        "business_interest": _text(payload.get("businessInterest")),
        "adults": _text(payload.get("adults")),
        "children": _text(payload.get("children")),
        "child_ages": _text(payload.get("childAges")),
        "tracks": _text(payload.get("tracks")),
        "tracks_labels": _text(payload.get("tracksLabels")),
        "contact": _text(payload.get("contact")),
        "language": _text(payload.get("lang")),
        "user_agent": _text(user_agent),
        "raw_json": payload,
    }

    cols = (
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
        "raw_json",
    )

    if _is_postgres():
        from psycopg.types.json import Json

        placeholders = ", ".join(["%s"] * len(cols))
        sql = (
            f"INSERT INTO pre_registrations ({', '.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        values = [
            row["full_name"],
            row["phone"],
            row["wechat"],
            row["cant"],
            row["join_choice"],
            row["join_label"],
            row["other_dates"],
            row["companies"],
            row["business_interest"],
            row["adults"],
            row["children"],
            row["child_ages"],
            row["tracks"],
            row["tracks_labels"],
            row["contact"],
            row["language"],
            row["user_agent"],
            Json(row["raw_json"]),
        ]
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
        return

    created_at = datetime.now(timezone.utc).isoformat()
    sql = (
        f"INSERT INTO pre_registrations ({', '.join(cols)}, created_at) "
        f"VALUES ({', '.join(['?'] * (len(cols) + 1))})"
    )
    values = [
        row["full_name"],
        row["phone"],
        row["wechat"],
        1 if row["cant"] else 0,
        row["join_choice"],
        row["join_label"],
        row["other_dates"],
        row["companies"],
        row["business_interest"],
        row["adults"],
        row["children"],
        row["child_ages"],
        row["tracks"],
        row["tracks_labels"],
        row["contact"],
        row["language"],
        row["user_agent"],
        json.dumps(row["raw_json"], ensure_ascii=False),
        created_at,
    ]
    with _sqlite_conn() as conn:
        conn.execute(sql, values)


@app.post("/api/pre-register")
def pre_register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    # Honeypot: accept quietly without writing.
    if _text(data.get("website")):
        return jsonify({"ok": True})

    full_name = _text(data.get("fullName"))
    join_choice = _text(data.get("join"))
    if len(full_name) < 2 or not join_choice:
        return jsonify({"ok": False, "error": "validation"}), 400

    if join_choice != "cant":
        if len(_text(data.get("phone"))) < 5 or len(_text(data.get("wechat"))) < 2:
            return jsonify({"ok": False, "error": "validation"}), 400

    try:
        insert_registration(data, request.headers.get("User-Agent", ""))
    except Exception as exc:
        app.logger.exception("pre-register insert failed: %s", exc)
        return jsonify({"ok": False, "error": "db"}), 500

    return jsonify({"ok": True})


@app.get("/", defaults={"path": "index.html"})
@app.get("/<path:path>")
def static_files(path: str):
    target = (ROOT / path).resolve()
    if not str(target).startswith(str(ROOT)):
        return ("Not found", 404)
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        return ("Not found", 404)
    return send_from_directory(target.parent, target.name)


ensure_schema()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
