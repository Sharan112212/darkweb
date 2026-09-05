"""
CaptureRepository implementing persistence and lookup for raw ingest/scraper captures.
Conforms to App Data Flow §4 & §5 idempotency rules.
"""

import sqlite3
import uuid
from typing import Any, Dict, List, Optional
from db.repositories.base import BaseRepository


class CaptureRepository(BaseRepository):
    """
    Repository for managing scraper/collector raw capture records.
    """

    @property
    def table_name(self) -> str:
        return "captures"

    @property
    def primary_key(self) -> str:
        return "capture_id"

    def _find_duplicate(
        self,
        source_id: str,
        url: str,
        sha256: Optional[str],
        captured_at: str,
    ) -> Optional[Dict[str, Any]]:
        """Find an existing capture by its idempotency constraint key."""
        query = (
            "SELECT * FROM captures WHERE source_id = ? AND url = ? "
            "AND (sha256 = ? OR (sha256 IS NULL AND ? IS NULL)) "
            "AND captured_at = ?"
        )
        row = self.conn.fetchone(query, (source_id, url, sha256, sha256, captured_at))
        return self._format_row_for_read(row)

    def save(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist a Capture record.
        Returns the existing Capture record if duplicate constraint matches.
        """
        if hasattr(capture, "model_dump"):
            data = capture.model_dump()
        else:
            data = dict(capture)

        cap_id = data.get("capture_id") or f"cap_{uuid.uuid4().hex[:12]}"
        source_id = data.get("source_id", "")
        url = data.get("url", "")
        mode = data.get("mode", "tor_proxy")
        authorization_status = data.get("authorization_status", "approved")
        captured_at = str(data.get("captured_at", ""))
        source_claimed_time = data.get("source_claimed_time")
        http_status = data.get("http_status")
        content_type = data.get("content_type")
        sha256 = data.get("sha256")
        raw_object_reference = data.get("raw_object_reference")
        status = data.get("status", "succeeded")
        not_collected_reason = data.get("not_collected_reason")

        # Check existing by composite idempotency key first
        if source_id and url and captured_at:
            existing = self._find_duplicate(
                source_id=source_id,
                url=url,
                sha256=sha256,
                captured_at=captured_at,
            )
            if existing:
                return existing

        # Check existing by ID if provided
        if "capture_id" in data and data["capture_id"]:
            existing_by_id = self.get_by_id(data["capture_id"])
            if existing_by_id:
                return existing_by_id

        insert_sql = """
        INSERT INTO captures (
            capture_id, source_id, url, mode, authorization_status,
            captured_at, source_claimed_time, http_status, content_type,
            sha256, raw_object_reference, status, not_collected_reason
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """
        params = (
            cap_id, source_id, url, mode, authorization_status,
            captured_at, source_claimed_time, http_status, content_type,
            sha256, raw_object_reference, status, not_collected_reason,
        )

        try:
            self.conn.execute(insert_sql, params)
            self.conn.commit()
            return self.get_by_id(cap_id)  # type: ignore
        except (sqlite3.IntegrityError, Exception) as exc:
            self.conn.rollback()
            existing = self._find_duplicate(
                source_id=source_id,
                url=url,
                sha256=sha256,
                captured_at=captured_at,
            )
            if existing:
                return existing
            existing_by_id = self.get_by_id(cap_id)
            if existing_by_id:
                return existing_by_id
            raise exc

    def list_by_source(self, source_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List captures originating from a specific source."""
        query = "SELECT * FROM captures WHERE source_id = ? ORDER BY captured_at DESC LIMIT ?"
        rows = self.conn.fetchall(query, (source_id, limit))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def get_by_hash(self, sha256: str) -> Optional[Dict[str, Any]]:
        """Find capture by SHA256 payload checksum."""
        query = "SELECT * FROM captures WHERE sha256 = ? LIMIT 1"
        row = self.conn.fetchone(query, (sha256,))
        return self._format_row_for_read(row)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List captures ordered by capture time descending."""
        query = f"SELECT * FROM {self.table_name} ORDER BY captured_at DESC LIMIT ? OFFSET ?"
        rows = self.conn.fetchall(query, (limit, offset))
        return [self._format_row_for_read(r) for r in rows if r is not None]
