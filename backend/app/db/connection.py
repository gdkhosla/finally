"""SQLite connection factory."""
import os
import sqlite3
from pathlib import Path

# Default DB path (repo root db/ for local dev, /app/db in container). The env var
# FINALLY_DB_PATH is the authoritative override and is read at connection time, so it
# takes effect even when set after this module is imported (e.g. in tests).
_DEFAULT_DB_PATH = str(Path(__file__).resolve().parents[3] / "db" / "finally.db")
DB_PATH = _DEFAULT_DB_PATH


def get_conn() -> sqlite3.Connection:
    """Return a short-lived SQLite connection with dict row factory."""
    path = os.environ.get("FINALLY_DB_PATH") or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
