"""
EvidenceRepository implementing persistence and retrieval for EvidenceUnits.
Enforces idempotency constraints matching App Data Flow §4 & §5.
"""

import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Set
from db.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository):
    """
    Repository for managing atomic EvidenceUnits.
    """

    @property
    def table_name(self) -> str:
        return "evidence_units"

    @property
    def primary_key(self) -> str:
        return "evidence_id"

    @property
    def json_columns(self) -> Set[str]:
        return {"limitations_json", "model_metadata_json"}

    def _find_duplicate(
        self,
        source: str,
        source_version: str,
        capture_id: Optional[str],
        indicator_type: str,
        indicator_value: str,
        left_entity_id: str,
        right_entity_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Find an existing evidence unit by its idempotency constraint key."""
        query = (
            "SELECT * FROM evidence_units WHERE source = ? AND source_version = ? "
            "AND (capture_id = ? OR (capture_id IS NULL AND ? IS NULL)) "
            "AND indicator_type = ? AND indicator_value = ? "
            "AND left_entity_id = ? AND right_entity_id = ?"
        )
        row = self.conn.fetchone(
            query,
            (
                source,
                source_version,
                capture_id,
                capture_id,
                indicator_type,
                indicator_value,
                left_entity_id,
                right_entity_id,
            ),
        )
        return self._format_row_for_read(row)

    def _format_row_for_read(self, row: Optional[Dict[str, Any]]) -> Any:
        formatted = super()._format_row_for_read(row)
        if formatted is None:
            return None
        if "linked_entities" not in formatted or not formatted["linked_entities"]:
            left = formatted.get("left_entity_id", "")
            right = formatted.get("right_entity_id", "")
            formatted["linked_entities"] = [left, right] if (left or right) else []
        try:
            from models.evidence import EvidenceUnit
            if "confidence_weight" in formatted and formatted["confidence_weight"] is not None:
                formatted["confidence_weight"] = float(formatted["confidence_weight"])
            if "time_confidence" in formatted and formatted["time_confidence"] is not None:
                try:
                    formatted["time_confidence"] = float(formatted["time_confidence"])
                except (ValueError, TypeError):
                    formatted["time_confidence"] = 1.0
            return EvidenceUnit(**formatted)
        except Exception:
            return formatted

    def save(self, evidence_unit: Any) -> Any:
        """
        Persist an EvidenceUnit.
        If a duplicate constraint violation occurs (same composite idempotency key or primary key),
        the existing EvidenceUnit is retrieved and returned.
        """
        if hasattr(evidence_unit, "model_dump"):
            unit = evidence_unit.model_dump()
        elif hasattr(evidence_unit, "dict"):
            unit = evidence_unit.dict()
        else:
            unit = dict(evidence_unit)

        # Ensure ID
        ev_id = unit.get("evidence_id") or f"ev_{uuid.uuid4().hex[:12]}"
        schema_version = unit.get("schema_version", "1.0")
        capture_id = unit.get("capture_id")
        source = unit.get("source", "")
        source_version = unit.get("source_version", "1.0")
        indicator_type = unit.get("indicator_type", "")
        indicator_value = unit.get("indicator_value", "")
        indicator_role = unit.get("indicator_role")
        left_entity_id = unit.get("left_entity_id", "")
        right_entity_id = unit.get("right_entity_id", "")
        linked_entities = unit.get("linked_entities") or []
        if (not left_entity_id or not right_entity_id) and linked_entities:
            if len(linked_entities) >= 2:
                left_entity_id = min(str(linked_entities[0]), str(linked_entities[1]))
                right_entity_id = max(str(linked_entities[0]), str(linked_entities[1]))
            elif len(linked_entities) == 1:
                left_entity_id = str(linked_entities[0])
                right_entity_id = str(linked_entities[0])
        unit["left_entity_id"] = left_entity_id
        unit["right_entity_id"] = right_entity_id
        confidence_weight = float(unit.get("confidence_weight", 1.0))
        source_reliability = float(unit.get("source_reliability", 1.0))
        extraction_confidence = float(unit.get("extraction_confidence", 1.0))
        source_claimed_time = unit.get("source_claimed_time")
        observation_date = unit.get("observation_date")
        captured_at = unit.get("captured_at")
        time_confidence = unit.get("time_confidence")
        source_url = unit.get("source_url")
        raw_evidence_hash = unit.get("raw_evidence_hash")
        raw_evidence_reference = unit.get("raw_evidence_reference")
        independence_group_id = unit.get("independence_group_id")
        collector_mode = unit.get("collector_mode")
        processing_status = unit.get("processing_status", "processed")
        explanation = unit.get("explanation")
        context_excerpt = unit.get("context_excerpt")

        # JSON fields handling
        limitations = unit.get("limitations_json") or unit.get("limitations", [])
        limitations_json = self._serialize_json(limitations, default_str="[]")

        model_metadata = unit.get("model_metadata_json") or unit.get("model_metadata", {})
        model_metadata_json = self._serialize_json(model_metadata, default_str="{}")

        # Check existing by composite unique constraint first
        existing = self._find_duplicate(
            source=source,
            source_version=source_version,
            capture_id=capture_id,
            indicator_type=indicator_type,
            indicator_value=indicator_value,
            left_entity_id=left_entity_id,
            right_entity_id=right_entity_id,
        )
        if existing:
            return existing

        # Check existing by ID if specified
        if "evidence_id" in unit and unit["evidence_id"]:
            existing_by_id = self.get_by_id(unit["evidence_id"])
            if existing_by_id:
                return existing_by_id

        insert_sql = """
        INSERT INTO evidence_units (
            evidence_id, schema_version, capture_id, source, source_version,
            indicator_type, indicator_value, indicator_role, left_entity_id, right_entity_id,
            confidence_weight, source_reliability, extraction_confidence, source_claimed_time,
            observation_date, captured_at, time_confidence, source_url, raw_evidence_hash,
            raw_evidence_reference, independence_group_id, collector_mode, processing_status,
            explanation, limitations_json, context_excerpt, model_metadata_json
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """
        params = (
            ev_id, schema_version, capture_id, source, source_version,
            indicator_type, indicator_value, indicator_role, left_entity_id, right_entity_id,
            confidence_weight, source_reliability, extraction_confidence, source_claimed_time,
            observation_date, captured_at, time_confidence, source_url, raw_evidence_hash,
            raw_evidence_reference, independence_group_id, collector_mode, processing_status,
            explanation, limitations_json, context_excerpt, model_metadata_json,
        )

        try:
            self.conn.execute(insert_sql, params)
            self.conn.commit()
            return self.get_by_id(ev_id)  # type: ignore
        except (sqlite3.IntegrityError, Exception) as exc:
            self.conn.rollback()
            # If constraint violation, retrieve and return the existing record
            existing = self._find_duplicate(
                source=source,
                source_version=source_version,
                capture_id=capture_id,
                indicator_type=indicator_type,
                indicator_value=indicator_value,
                left_entity_id=left_entity_id,
                right_entity_id=right_entity_id,
            )
            if existing:
                return existing
            existing_by_id = self.get_by_id(ev_id)
            if existing_by_id:
                return existing_by_id
            raise exc

    def list_by_pair(self, left_id: str, right_id: str) -> List[Dict[str, Any]]:
        """List all evidence units correlating an entity pair in either direction."""
        query = """
        SELECT * FROM evidence_units
        WHERE (left_entity_id = ? AND right_entity_id = ?)
           OR (left_entity_id = ? AND right_entity_id = ?)
        ORDER BY created_at DESC
        """
        rows = self.conn.fetchall(query, (left_id, right_id, right_id, left_id))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def list_by_capture(self, capture_id: str) -> List[Dict[str, Any]]:
        """List all evidence units originating from a specific capture."""
        query = "SELECT * FROM evidence_units WHERE capture_id = ? ORDER BY created_at DESC"
        rows = self.conn.fetchall(query, (capture_id,))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def list_by_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """List all evidence units where the entity is either left or right."""
        query = """
        SELECT * FROM evidence_units
        WHERE left_entity_id = ? OR right_entity_id = ?
        ORDER BY created_at DESC
        """
        rows = self.conn.fetchall(query, (entity_id, entity_id))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List evidence units ordered by creation date descending."""
        query = f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.conn.fetchall(query, (limit, offset))
        return [self._format_row_for_read(r) for r in rows if r is not None]
