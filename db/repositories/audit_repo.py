"""
AuditRepository implementing append-only immutable audit logging.
Conforms to App Data Flow §4 & §5 idempotency rules.
"""

from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional, Set
import uuid
from db.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """
    Repository for append-only audit event logging and administrative inspection.
    """

    @property
    def table_name(self) -> str:
        return "audit_events"

    @property
    def primary_key(self) -> str:
        return "event_id"

    @property
    def json_columns(self) -> Set[str]:
        return {"details_json"}

    def _find_duplicate(
        self,
        request_id: str,
        action: str,
        object_id: str,
        timestamp: str,
    ) -> Optional[Dict[str, Any]]:
        """Find an existing audit event by its idempotency constraint key."""
        query = (
            "SELECT * FROM audit_events "
            "WHERE request_id = ? AND action = ? AND object_id = ? AND timestamp = ?"
        )
        row = self.conn.fetchone(query, (request_id, action, object_id, timestamp))
        return self._format_row_for_read(row)

    def append(self, audit_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append an immutable audit event to the log.
        Returns the existing event if duplicate constraint matches.
        """
        data = dict(audit_event)

        event_id = data.get("event_id") or f"aud_{uuid.uuid4().hex[:12]}"
        request_id = data.get("request_id", "req_system")
        user_id = data.get("user_id", "system")
        action = data.get("action", "")
        object_id = data.get("object_id", "")
        ts = data.get("timestamp")
        if not ts:
            ts = datetime.now(timezone.utc).isoformat()
        else:
            ts = str(ts)

        details = data.get("details_json") or data.get("details", {})
        details_json = self._serialize_json(details, default_str="{}")

        # Check existing duplicate first
        existing = self._find_duplicate(
            request_id=request_id,
            action=action,
            object_id=object_id,
            timestamp=ts,
        )
        if existing:
            return existing

        insert_sql = """
        INSERT INTO audit_events (
            event_id, request_id, user_id, action, object_id, timestamp, details_json
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?
        )
        """
        params = (event_id, request_id, user_id, action, object_id, ts, details_json)

        try:
            self.conn.execute(insert_sql, params)
            self.conn.commit()
            return self.get_by_id(event_id)  # type: ignore
        except (sqlite3.IntegrityError, Exception) as exc:
            self.conn.rollback()
            existing = self._find_duplicate(
                request_id=request_id,
                action=action,
                object_id=object_id,
                timestamp=ts,
            )
            if existing:
                return existing
            existing_by_id = self.get_by_id(event_id)
            if existing_by_id:
                return existing_by_id
            raise exc

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Alias to satisfy BaseRepository abstract interface."""
        return self.append(entity)

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        object_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query audit events with optional filtering by object, user, or action.
        Ordered by timestamp descending.
        """
        clauses = []
        params: List[Any] = []

        if object_id:
            clauses.append("object_id = ?")
            params.append(object_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if action:
            clauses.append("action = ?")
            params.append(action)

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM audit_events {where_str} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.fetchall(query, tuple(params))
        return [self._format_row_for_read(r) for r in rows if r is not None]
