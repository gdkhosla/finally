"""Repository functions — all DB reads and writes go through here."""
import json
import uuid
from datetime import datetime, timezone

from app.db.connection import get_conn

_USER = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    return dict(row)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_profile() -> dict:
    """Return {id, cash_balance, created_at} for the default user."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?", (_USER,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def set_cash(new_balance: float) -> None:
    """Update cash balance for the default user."""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_balance, _USER)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def list_watchlist() -> list[str]:
    """Return tickers on the watchlist, ordered by added_at."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at", (_USER,)
        ).fetchall()
        return [r["ticker"] for r in rows]
    finally:
        conn.close()


def watchlist_has(ticker: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?", (_USER, ticker)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def add_watchlist(ticker: str) -> None:
    """Add ticker to watchlist. Idempotent (UNIQUE constraint)."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), _USER, ticker, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_watchlist(ticker: str) -> None:
    """Remove ticker from watchlist."""
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (_USER, ticker)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def get_position(ticker: str) -> dict | None:
    """Return {ticker, quantity, avg_cost} or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (_USER, ticker),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_positions() -> list[dict]:
    """Return all positions as list of {ticker, quantity, avg_cost}."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker",
            (_USER,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def upsert_position(ticker: str, quantity: float, avg_cost: float) -> None:
    """Insert or update a position. Caller is responsible for rounding quantity."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                quantity   = excluded.quantity,
                avg_cost   = excluded.avg_cost,
                updated_at = excluded.updated_at
            """,
            (str(uuid.uuid4()), _USER, ticker, quantity, avg_cost, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def delete_position(ticker: str) -> None:
    """Remove position row — called when quantity hits 0 on a full sell."""
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (_USER, ticker)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

def record_trade(ticker: str, side: str, quantity: float, price: float) -> dict:
    """Append a trade record and return the stored row as a dict."""
    trade_id = str(uuid.uuid4())
    executed_at = _now()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, _USER, ticker, side, quantity, price, executed_at),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": trade_id,
        "user_id": _USER,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": executed_at,
    }


def list_trades(limit: int | None = None) -> list[dict]:
    """Return trades ordered newest-first. Pass limit to cap results."""
    conn = get_conn()
    try:
        if limit is not None:
            rows = conn.execute(
                "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC LIMIT ?",
                (_USER, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC",
                (_USER,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Portfolio snapshots
# ---------------------------------------------------------------------------

def record_snapshot(total_value: float) -> None:
    """Record a portfolio value snapshot."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), _USER, total_value, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_snapshots(limit: int = 500) -> list[dict]:
    """Return most recent N snapshots in chronological order."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT total_value, recorded_at FROM (
                SELECT total_value, recorded_at
                FROM portfolio_snapshots
                WHERE user_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
            ) ORDER BY recorded_at ASC
            """,
            (_USER, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------

def list_messages(limit: int = 20) -> list[dict]:
    """Return last N messages in chronological order."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, role, content, actions, created_at FROM (
                SELECT id, user_id, role, content, actions, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (_USER, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def add_message(role: str, content: str, actions=None) -> dict:
    """Store a chat message. actions is JSON-serialized if not None."""
    msg_id = str(uuid.uuid4())
    created_at = _now()
    actions_json = json.dumps(actions) if actions is not None else None
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, _USER, role, content, actions_json, created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": msg_id,
        "user_id": _USER,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }
