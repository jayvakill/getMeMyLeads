import sqlite3
import os
from datetime import datetime

DB_PATH = "data/startup_signals.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS startup_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT,
    website TEXT,
    category TEXT,
    stage TEXT,
    signal_type TEXT,
    signal_details TEXT,
    job_title TEXT,
    funding_amount TEXT,
    funding_date TEXT,
    relevant_person_name TEXT,
    relevant_person_title TEXT,
    source_name TEXT,
    source_url TEXT,
    context_summary TEXT,
    score INTEGER DEFAULT 0,
    date_found TEXT,
    last_seen TEXT
)
"""


def get_conn():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(CREATE_TABLE)
        conn.commit()


def insert_signal(data):
    fields = [
        "company_name", "website", "category", "stage", "signal_type",
        "signal_details", "job_title", "funding_amount", "funding_date",
        "relevant_person_name", "relevant_person_title", "source_name",
        "source_url", "context_summary", "score", "date_found", "last_seen",
    ]
    row = {f: data.get(f, "") for f in fields}
    row["date_found"] = row.get("date_found") or datetime.now().strftime("%Y-%m-%d")
    row["last_seen"] = datetime.now().strftime("%Y-%m-%d")

    placeholders = ", ".join(f":{f}" for f in fields)
    cols = ", ".join(fields)
    sql = f"INSERT INTO startup_signals ({cols}) VALUES ({placeholders})"

    with get_conn() as conn:
        cur = conn.execute(sql, row)
        conn.commit()
        return cur.lastrowid


def update_signal(signal_id, data):
    updateable = [
        "category", "stage", "signal_type", "signal_details", "job_title",
        "funding_amount", "funding_date", "relevant_person_name",
        "relevant_person_title", "source_name", "source_url",
        "context_summary", "score", "last_seen",
    ]
    sets = []
    vals = {}
    for f in updateable:
        if f in data:
            sets.append(f"{f} = :{f}")
            vals[f] = data[f]
    vals["id"] = signal_id
    vals["last_seen"] = datetime.now().strftime("%Y-%m-%d")
    sets.append("last_seen = :last_seen")

    sql = f"UPDATE startup_signals SET {', '.join(sets)} WHERE id = :id"
    with get_conn() as conn:
        conn.execute(sql, vals)
        conn.commit()


def get_by_domain(domain):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM startup_signals WHERE website LIKE ?",
            (f"%{domain}%",)
        ).fetchone()
        return dict(row) if row else None


def get_by_name(company_name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM startup_signals WHERE LOWER(company_name) = LOWER(?)",
            (company_name,)
        ).fetchone()
        return dict(row) if row else None


def get_signals_for_date(date_str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM startup_signals WHERE date_found = ? ORDER BY score DESC",
            (date_str,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_signals():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM startup_signals ORDER BY score DESC, date_found DESC"
        ).fetchall()
        return [dict(r) for r in rows]
