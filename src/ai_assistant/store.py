"""
SQLite store for AI Assistant.

Tables:
- ai_docs: Documents (code, doc, issue, commit, diff)
- ai_chunks: Text chunks with embeddings
- ai_feedback: Developer feedback for improvement
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class AIStore:
    """SQLite-based storage for AI assistant data."""

    def __init__(self, db_path: str = "ai_assistant.db"):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a new SQLite connection to the configured database."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Initialize database tables and indexes."""
        print(f"DEBUG: Connecting to DB: {self.db_path}")
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_docs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT CHECK(kind IN ('code','doc','issue','commit','diff')) NOT NULL,
                    uri TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    ord INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    emb BLOB,
                    FOREIGN KEY (doc_id) REFERENCES ai_docs(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_chunks_doc_id ON ai_chunks(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_docs_kind ON ai_docs(kind)")
            conn.commit()
        finally:
            conn.close()

    def upsert_doc(self, kind: str, uri: str, title: str, content: str) -> int:
        """Upsert a document. Returns doc_id."""
        updated_at = datetime.utcnow().isoformat()
        conn = self._connect()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO ai_docs (kind, uri, title, content, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(uri) DO UPDATE SET
                        title = excluded.title,
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    (kind, uri, title, content, updated_at),
                )
                doc_id = cursor.lastrowid
                if doc_id == 0:  # Conflict, get existing id
                    cursor.execute("SELECT id FROM ai_docs WHERE uri = ?", (uri,))
                    doc_id = cursor.fetchone()[0]
                conn.commit()
                assert doc_id is not None
                return doc_id
            finally:
                cursor.close()
        finally:
            conn.close()

    def upsert_chunks(self, doc_id: int, chunks: List[str], embeddings: Optional[List[bytes]] = None) -> None:
        """Upsert chunks for a document. Embeddings as float32 bytes."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM ai_chunks WHERE doc_id = ?", (doc_id,))
                for i, chunk in enumerate(chunks):
                    emb = embeddings[i] if embeddings else None
                    cursor.execute(
                        """
                        INSERT INTO ai_chunks (doc_id, ord, text, emb)
                        VALUES (?, ?, ?, ?)
                        """,
                        (doc_id, i, chunk, emb),
                    )
                conn.commit()
            finally:
                cursor.close()
        finally:
            conn.close()

    def get_chunks_for_doc(self, doc_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, ord, text, emb FROM ai_chunks
                WHERE doc_id = ? ORDER BY ord
                """,
                (doc_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Get all chunks with doc info."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT c.id, c.doc_id, c.ord, c.text, c.emb,
                       d.kind, d.uri, d.title
                FROM ai_chunks c
                JOIN ai_docs d ON c.doc_id = d.id
                ORDER BY c.doc_id, c.ord
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_doc(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Get document by id."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ai_docs WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_docs_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        """Get all documents of a kind."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ai_docs WHERE kind = ?", (kind,))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_feedback(self, kind: str, payload: Dict[str, Any]) -> int:
        """Add feedback entry. Returns feedback_id."""
        created_at = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)
        conn = self._connect()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO ai_feedback (kind, payload, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (kind, payload_json, created_at),
                )
                conn.commit()
                feedback_id = cursor.lastrowid
                assert feedback_id is not None
                return feedback_id
            finally:
                cursor.close()
        finally:
            conn.close()

    def get_status(self) -> Dict[str, Any]:
        """Get store status."""
        conn = self._connect()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM ai_docs")
            docs_count = cursor.fetchone()[0]
            cursor.close()
            cursor = conn.execute("SELECT COUNT(*) FROM ai_chunks")
            chunks_count = cursor.fetchone()[0]
            cursor.close()
            cursor = conn.execute(
                """
                SELECT MAX(updated_at) FROM ai_docs
                """
            )
            last_updated = cursor.fetchone()[0]
            cursor.close()
            return {"docs": docs_count, "chunks": chunks_count, "last_indexed_at": last_updated}
        finally:
            conn.close()
