"""SQLite helpers for persisting already-processed deal IDs."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator


class DealDatabase:
    """Encapsulates CRUD operations for the seen_deals table."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_deals (
                    deal_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def has_seen(self, deal_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT 1 FROM seen_deals WHERE deal_id = ? LIMIT 1",
                (deal_id,),
            )
            return cursor.fetchone() is not None

    def mark_seen(self, deal_id: str, title: str, link: str) -> None:
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO seen_deals (deal_id, title, link, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (deal_id, title, link, timestamp),
            )
            connection.commit()
