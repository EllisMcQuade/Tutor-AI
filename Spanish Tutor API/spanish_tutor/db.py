import sqlite3
import os
from datetime import datetime

# Always create progress.db next to this file, regardless of working directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.db")


def _connect() -> sqlite3.Connection:
    """Open a connection with foreign key support enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't already exist. Safe to call every startup."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT    NOT NULL,
                turns       INTEGER NOT NULL DEFAULT 0,
                summary     TEXT
            );

            CREATE TABLE IF NOT EXISTS corrections (
                correction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id     INTEGER NOT NULL REFERENCES sessions(session_id),
                turn_number    INTEGER NOT NULL,
                user_input     TEXT    NOT NULL,
                correction     TEXT    NOT NULL,
                logged_at      TEXT    NOT NULL
            );
        """)


def create_session() -> int:
    """
    Start a new session and return its session_id.
    Call this once at the beginning of each conversation.
    """
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)",
            (datetime.now().isoformat(sep=" ", timespec="seconds"),),
        )
        return cur.lastrowid


def log_correction(session_id: int, turn_number: int, user_input: str, correction: str) -> None:
    """
    Store a single correction for a given turn.
    Call this whenever Claude returns a non-empty correction block.

    session_id  -- from create_session()
    turn_number -- 1-based counter, increment each time the user sends a message
    user_input  -- what the student typed or said
    correction  -- the English correction text extracted from Claude's reply
    """
    with _connect() as conn:
        conn.execute(
            """INSERT INTO corrections
               (session_id, turn_number, user_input, correction, logged_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                session_id,
                turn_number,
                user_input,
                correction,
                datetime.now().isoformat(sep=" ", timespec="seconds"),
            ),
        )


def save_summary(session_id: int, summary: str, turns: int) -> None:
    """
    Write the Claude-generated session summary and final turn count.
    Call this when the user ends a session.

    session_id -- from create_session()
    summary    -- a short paragraph Claude wrote summarising the session
    turns      -- total number of conversation turns
    """
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET summary = ?, turns = ? WHERE session_id = ?",
            (summary, turns, session_id),
        )


def get_session(session_id: int) -> dict | None:
    """Return a session row as a dict, or None if not found."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def get_corrections(session_id: int) -> list[dict]:
    """Return all corrections for a session, ordered by turn number."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM corrections WHERE session_id = ? ORDER BY turn_number",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# Initialise on import so tables always exist before anything else runs
init_db()
