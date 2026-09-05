"""
CaseRepository (Branch 5): analyst case management.

A case is an analyst-owned collection of candidate links / entities plus notes.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import uuid
from db.repositories.base import BaseRepository


class CaseRepository(BaseRepository):

    @property
    def table_name(self) -> str:
        return "cases"

    @property
    def primary_key(self) -> str:
        return "case_id"

    @property
    def json_columns(self) -> Set[str]:
        return {"link_ids_json", "entity_ids_json", "notes_json"}

    def create_case(self, data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data)
        case_id = d.get("case_id") or f"case_{uuid.uuid4().hex[:12]}"
        title = d.get("title", "")
        description = d.get("description", "")
        status = d.get("status", "open")
        owner = d.get("owner", "system")
        link_ids = self._serialize_json(d.get("link_ids", []), default_str="[]")
        entity_ids = self._serialize_json(d.get("entity_ids", []), default_str="[]")
        notes = self._serialize_json(d.get("notes", []), default_str="[]")

        self.conn.execute(
            """
            INSERT INTO cases (case_id, title, description, status, owner,
                               link_ids_json, entity_ids_json, notes_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, title, description, status, owner, link_ids, entity_ids, notes),
        )
        self.conn.commit()
        return self.get_by_id(case_id)  # type: ignore

    def add_note(self, case_id: str, author: str, text: str) -> Optional[Dict[str, Any]]:
        case = self.get_by_id(case_id)
        if not case:
            return None
        notes = case.get("notes_json") or case.get("notes") or []
        if isinstance(notes, str):
            notes = self._deserialize_json(notes, default=[])
        notes.append({
            "author": author,
            "text": text,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.conn.execute(
            "UPDATE cases SET notes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE case_id = ?",
            (self._serialize_json(notes, default_str="[]"), case_id),
        )
        self.conn.commit()
        return self.get_by_id(case_id)

    def list_by_owner(self, owner: str, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.conn.fetchall(
            "SELECT * FROM cases WHERE owner = ? ORDER BY created_at DESC LIMIT ?", (owner, limit)
        )
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        return self.create_case(entity)
