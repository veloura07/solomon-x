"""
Solomon X Hot Memory Cache (L1/L2).
SQLite-backed database for quick conversation turn retrieval and local session buffers.
"""

import sqlite3
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("solomon.memory.hot")

class SQLiteCache:
    """
    Volatile session sensory and conversation database cache.
    Designed for sub-10ms writes and reads.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path: str = db_path
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Sets up the table schemas for fast access and indexing."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hot_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    expiration REAL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON hot_cache (timestamp)
            """)
            conn.commit()

    def set(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        """Stores a serialized sensory block or message in the hot cache."""
        import time
        timestamp = time.time()
        expiration = (timestamp + ttl_seconds) if ttl_seconds else None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO hot_cache (key, value, timestamp, expiration) VALUES (?, ?, ?, ?)",
                (key, value, timestamp, expiration)
            )
            conn.commit()
        logger.debug(f"Cached key '{key}' in L1 store.")

    def get(self, key: str) -> Optional[str]:
        """Retrieves a cached value if it is not expired."""
        import time
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value, expiration FROM hot_cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                value, expiration = row
                if expiration and now > expiration:
                    self.delete(key)
                    return None
                return value
        return None

    def delete(self, key: str) -> None:
        """Evicts a key from the hot cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hot_cache WHERE key = ?", (key,))
            conn.commit()

    def clear_expired(self) -> None:
        """Cleans up expired keys from the database."""
        import time
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hot_cache WHERE expiration IS NOT NULL AND expiration < ?", (now,))
            conn.commit()
