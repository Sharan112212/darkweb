"""
Abstract Base Repository defining the common persistence and retrieval interface.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Union
from db.connection import DatabaseConnection, get_connection


class BaseRepository(ABC):
    """
    Abstract generic base repository for database entities.
    """

    def __init__(
        self,
        connection: Optional[Union[DatabaseConnection, Any]] = None,
        db_path_or_url: Optional[str] = None,
    ):
        if connection is not None:
            self.conn = get_connection(connection)
        else:
            self.conn = get_connection(db_path_or_url)

    @property
    @abstractmethod
    def table_name(self) -> str:
        """The target database table name."""

    @property
    @abstractmethod
    def primary_key(self) -> str:
        """The primary key column name for this table."""

    @property
    def json_columns(self) -> Set[str]:
        """Set of column names that store serialized JSON data."""
        return set()

    def _serialize_json(self, value: Any, default_str: str = "{}") -> Optional[str]:
        """Serialize a dict/list to a JSON string. Preserves strings or returns default."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            return value
        return default_str

    def _deserialize_json(self, value: Any, default: Any = None) -> Any:
        """Parse a JSON string into a Python dict/list. Returns default if None or invalid."""
        if value is None:
            return default if default is not None else {}
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default if default is not None else {}
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default if default is not None else value
        return default if default is not None else {}

    def _format_row_for_read(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Processes a raw database row: parses JSON columns into native python structures
        and adds convenience accessors without the '_json' suffix.
        """
        if row is None:
            return None
        item = dict(row)
        for col in self.json_columns:
            if col in item:
                parsed = self._deserialize_json(
                    item[col],
                    default=[] if col.endswith("ids_json") or "limitations" in col else {},
                )
                item[col] = parsed
                # Convenience alias (e.g. 'limitations' for 'limitations_json')
                if col.endswith("_json"):
                    alias = col[:-5]
                    if alias not in item:
                        item[alias] = parsed
        return item

    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single entity by its primary key."""
        query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?"
        row = self.conn.fetchone(query, (entity_id,))
        return self._format_row_for_read(row)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List entities with pagination."""
        query = f"SELECT * FROM {self.table_name} LIMIT ? OFFSET ?"
        rows = self.conn.fetchall(query, (limit, offset))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def delete(self, entity_id: str) -> bool:
        """Delete an entity by its primary key. Returns True if a record was removed."""
        query = f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?"
        cur = self.conn.execute(query, (entity_id,))
        self.conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
        return deleted

    def count(self) -> int:
        """Return total number of rows in the table."""
        query = f"SELECT COUNT(*) AS total FROM {self.table_name}"
        row = self.conn.fetchone(query)
        if row:
            return int(row.get("total", 0))
        return 0

    @abstractmethod
    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Persist or update an entity."""
