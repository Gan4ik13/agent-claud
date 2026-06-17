import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    remind_at TIMESTAMP NOT NULL,
                    is_done INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_reminders_pending
                    ON reminders(user_id, is_done, remind_at);

                CREATE INDEX IF NOT EXISTS idx_notes_user
                    ON notes(user_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_history_user
                    ON chat_history(user_id, created_at DESC);
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- Notes ----

    def add_note(self, user_id: int, text: str, tags: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO notes (user_id, text, tags) VALUES (?, ?, ?)",
                (user_id, text, tags),
            )
            return cur.lastrowid

    def get_notes(self, user_id: int, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, tags, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_note(self, user_id: int, note_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM notes WHERE id = ? AND user_id = ?",
                (note_id, user_id),
            )
            return cur.rowcount > 0

    def search_notes(self, user_id: int, query: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, tags, created_at FROM notes WHERE user_id = ? AND (text LIKE ? OR tags LIKE ?) ORDER BY created_at DESC LIMIT 20",
                (user_id, f"%{query}%", f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Reminders ----

    def add_reminder(self, user_id: int, text: str, remind_at: datetime) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (user_id, text, remind_at) VALUES (?, ?, ?)",
                (user_id, text, remind_at.isoformat()),
            )
            return cur.lastrowid

    def get_pending_reminders(self, user_id: int) -> list[dict]:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, remind_at FROM reminders WHERE user_id = ? AND is_done = 0 AND remind_at <= ? ORDER BY remind_at",
                (user_id, now),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_reminders(self, user_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, remind_at, is_done FROM reminders WHERE user_id = ? ORDER BY remind_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def complete_reminder(self, reminder_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE reminders SET is_done = 1 WHERE id = ?",
                (reminder_id,),
            )
            return cur.rowcount > 0

    def delete_reminder(self, user_id: int, reminder_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id),
            )
            return cur.rowcount > 0

    def get_due_reminders(self) -> list[dict]:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, user_id, text, remind_at FROM reminders WHERE is_done = 0 AND remind_at <= ?",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Chat History ----

    def add_message(self, user_id: int, role: str, content: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )

    def get_history(self, user_id: int, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def clear_history(self, user_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
