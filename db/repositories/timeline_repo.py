"""
TimelineRepository implementing persistence and timeline extraction for entities.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import uuid
from db.repositories.base import BaseRepository


class TimelineRepository(BaseRepository):
    """
    Repository for managing chronological timeline events for entities.
    """

    @property
    def table_name(self) -> str:
        return "timeline_events"

    @property
    def primary_key(self) -> str:
        return "event_id"

    @property
    def json_columns(self) -> Set[str]:
        return {"evidence_ids_json", "metadata_json"}

    def append(self, timeline_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a timeline event for an entity.
        """
        data = dict(timeline_event)
        event_id = data.get("event_id") or f"tl_{uuid.uuid4().hex[:12]}"
        event_type = data.get("event_type", "observation")
        entity_id = data.get("entity_id", "")
        ts = data.get("timestamp") or datetime.now(timezone.utc).isoformat()
        time_confidence = data.get("time_confidence", "exact")
        description = data.get("description", "")

        ev_ids = data.get("evidence_ids_json") or data.get("evidence_ids", [])
        evidence_ids_json = self._serialize_json(ev_ids, default_str="[]")

        meta = data.get("metadata_json") or data.get("metadata", {})
        metadata_json = self._serialize_json(meta, default_str="{}")

        insert_sql = """
        INSERT INTO timeline_events (
            event_id, event_type, entity_id, timestamp, time_confidence,
            description, evidence_ids_json, metadata_json
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?
        )
        """
        params = (
            event_id, event_type, entity_id, str(ts), time_confidence,
            description, evidence_ids_json, metadata_json,
        )
        self.conn.execute(insert_sql, params)
        self.conn.commit()
        return self.get_by_id(event_id)  # type: ignore

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Alias to satisfy BaseRepository abstract interface."""
        return self.append(entity)

    def list_by_entity(self, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve timeline events for an entity sorted chronologically."""
        query = "SELECT * FROM timeline_events WHERE entity_id = ? ORDER BY timestamp ASC LIMIT ?"
        rows = self.conn.fetchall(query, (entity_id, limit))
        return [self._format_row_for_read(r) for r in rows if r is not None]
