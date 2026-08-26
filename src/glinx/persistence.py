"""Data persistence layer for historical sensor data."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
import json
from datetime import datetime

from .models import GlinxMessage, EventMessage


class DataLogger:
    """Log sensor data and events to SQLite."""

    def __init__(self, db_path: str | Path = "glinx_data.db") -> None:
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
        # Messages table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                protocol TEXT NOT NULL,
                timestamp REAL NOT NULL,
                parsed JSON,
                enriched JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Events table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                label TEXT NOT NULL,
                priority TEXT NOT NULL,
                kind TEXT NOT NULL,
                description TEXT,
                timestamp REAL NOT NULL,
                payload JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for common queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(source_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_label ON events(label)")
        
        self.conn.commit()

    def log_message(self, message: GlinxMessage) -> None:
        """Log a sensor message."""
        if self.conn is None:
            return
        
        self.conn.execute(
            """
            INSERT INTO messages (source_id, protocol, timestamp, parsed, enriched)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message.source_id,
                message.protocol,
                message.timestamp,
                json.dumps(message.parsed),
                json.dumps(message.enriched),
            ),
        )
        self.conn.commit()

    def log_event(self, event: EventMessage) -> None:
        """Log an event."""
        if self.conn is None:
            return
        
        self.conn.execute(
            """
            INSERT INTO events (source_id, label, priority, kind, description, timestamp, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.source_id,
                event.label,
                event.priority,
                event.kind,
                event.description,
                event.timestamp,
                json.dumps(event.payload),
            ),
        )
        self.conn.commit()

    def query_messages(
        self,
        source_id: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query historical messages."""
        if self.conn is None:
            return []
        
        query = "SELECT * FROM messages WHERE 1=1"
        params: list[Any] = []
        
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        columns = [col[0] for col in cursor.description]
        
        results = []
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            result["parsed"] = json.loads(result["parsed"]) if result["parsed"] else {}
            result["enriched"] = json.loads(result["enriched"]) if result["enriched"] else {}
            results.append(result)
        
        return results

    def query_events(
        self,
        source_id: str | None = None,
        label: str | None = None,
        priority: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query historical events."""
        if self.conn is None:
            return []
        
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        
        if label:
            query += " AND label = ?"
            params.append(label)
        
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        columns = [col[0] for col in cursor.description]
        
        results = []
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            result["payload"] = json.loads(result["payload"]) if result["payload"] else {}
            results.append(result)
        
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        if self.conn is None:
            return {}
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM messages")
        message_count = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(DISTINCT source_id) FROM messages")
        source_count = cursor.fetchone()[0]
        
        return {
            "total_messages": message_count,
            "total_events": event_count,
            "unique_sources": source_count,
            "db_path": str(self.db_path),
        }

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> DataLogger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
