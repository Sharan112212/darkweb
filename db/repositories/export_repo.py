"""
ExportRepository (Branch 5): immutable export snapshots.

An export is a point-in-time snapshot (with SHA-256) of a scope of links/
entities, carrying the mandatory disclosure text. Snapshots are immutable so a
later change to the underlying data does not alter an already-created export
(EC-15 export-stability).
"""
import hashlib
import json
from typing import Any, Dict, List, Optional, Set
import uuid
from db.repositories.base import BaseRepository

DISCLOSURE = (
    "This system provides confidence-scored technical associations for authorized "
    "analyst review. It does not defeat Tor, establish a person's real-world identity, "
    "or replace legal/forensic investigation."
)


class ExportRepository(BaseRepository):

    @property
    def table_name(self) -> str:
        return "exports"

    @property
    def primary_key(self) -> str:
        return "export_id"

    @property
    def json_columns(self) -> Set[str]:
        return {"scope_json", "snapshot_json"}

    def create_export(self, data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data)
        export_id = d.get("export_id") or f"exp_{uuid.uuid4().hex[:12]}"
        export_type = d.get("export_type", "links")
        requested_by = d.get("requested_by", "system")
        scope = d.get("scope", {})
        snapshot = d.get("snapshot", {})
        snapshot_str = json.dumps(snapshot, sort_keys=True, default=str)
        snapshot_sha256 = hashlib.sha256(snapshot_str.encode()).hexdigest()

        self.conn.execute(
            """
            INSERT INTO exports (export_id, export_type, requested_by, scope_json,
                                 snapshot_json, snapshot_sha256, disclosure)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                export_id, export_type, requested_by,
                self._serialize_json(scope, default_str="{}"),
                self._serialize_json(snapshot, default_str="{}"),
                snapshot_sha256, DISCLOSURE,
            ),
        )
        self.conn.commit()
        return self.get_by_id(export_id)  # type: ignore

    def list_by_requester(self, requested_by: str, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.conn.fetchall(
            "SELECT * FROM exports WHERE requested_by = ? ORDER BY created_at DESC LIMIT ?",
            (requested_by, limit),
        )
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        return self.create_export(entity)
