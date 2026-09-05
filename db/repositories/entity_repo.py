"""
EntityRepository implementing persistence and canonical resolution for entities.
"""

from typing import Any, Dict, List, Optional
import uuid
from db.repositories.base import BaseRepository


class EntityRepository(BaseRepository):
    """
    Repository for managing canonical entities (threat actors, personas, wallets, fingerprints).
    """

    @property
    def table_name(self) -> str:
        return "entities"

    @property
    def primary_key(self) -> str:
        return "entity_id"

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist or update an Entity record.
        """
        data = dict(entity)
        entity_id = data.get("entity_id") or f"ent_{uuid.uuid4().hex[:12]}"
        entity_type = data.get("entity_type", "actor")
        canonical_name = data.get("canonical_name", "")
        display_name = data.get("display_name", canonical_name)
        normalized_name = data.get("normalized_name", canonical_name.strip().lower())
        category = data.get("category")

        existing = self.get_by_id(entity_id)
        if existing:
            update_sql = """
            UPDATE entities SET
                entity_type = ?,
                canonical_name = ?,
                display_name = ?,
                normalized_name = ?,
                category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE entity_id = ?
            """
            self.conn.execute(
                update_sql,
                (entity_type, canonical_name, display_name, normalized_name, category, entity_id),
            )
        else:
            insert_sql = """
            INSERT INTO entities (
                entity_id, entity_type, canonical_name, display_name,
                normalized_name, category
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?
            )
            """
            self.conn.execute(
                insert_sql,
                (entity_id, entity_type, canonical_name, display_name, normalized_name, category),
            )

        self.conn.commit()
        return self.get_by_id(entity_id)  # type: ignore

    def get_by_canonical_name(self, canonical_name: str) -> Optional[Dict[str, Any]]:
        """Find entity by exact canonical name."""
        query = "SELECT * FROM entities WHERE canonical_name = ? LIMIT 1"
        row = self.conn.fetchone(query, (canonical_name,))
        return self._format_row_for_read(row)

    def get_by_normalized_name(self, normalized_name: str) -> Optional[Dict[str, Any]]:
        """Find entity by normalized name."""
        query = "SELECT * FROM entities WHERE normalized_name = ? LIMIT 1"
        row = self.conn.fetchone(query, (normalized_name.strip().lower(),))
        return self._format_row_for_read(row)

    def list_by_type(self, entity_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List entities filtered by entity_type."""
        query = "SELECT * FROM entities WHERE entity_type = ? ORDER BY canonical_name ASC LIMIT ?"
        rows = self.conn.fetchall(query, (entity_type, limit))
        return [self._format_row_for_read(r) for r in rows if r is not None]
