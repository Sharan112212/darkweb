"""
LinkRepository implementing persistence and versioning for CandidateLinks.
Manages candidate_links and candidate_link_versions tables.
"""

import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Set
from db.repositories.base import BaseRepository


class LinkRepository(BaseRepository):
    """
    Repository for candidate correlation links and immutable link version snapshots.
    """

    @property
    def table_name(self) -> str:
        return "candidate_links"

    @property
    def primary_key(self) -> str:
        return "link_id"

    @property
    def json_columns(self) -> Set[str]:
        return {
            "category_breakdown_json",
            "evidence_ids_json",
            "competing_link_ids_json",
            "limitations_json",
        }

    def _find_duplicate(
        self,
        left_entity_id: str,
        right_entity_id: str,
        score_model_version: str,
        calculation_input_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """Find an existing link by its idempotency constraint key."""
        query = (
            "SELECT * FROM candidate_links "
            "WHERE left_entity_id = ? AND right_entity_id = ? "
            "AND score_model_version = ? AND calculation_input_hash = ?"
        )
        row = self.conn.fetchone(
            query,
            (left_entity_id, right_entity_id, score_model_version, calculation_input_hash),
        )
        return self._format_row_for_read(row)

    def save_candidate_link(self, link: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist a CandidateLink.
        Always creates a corresponding version record in candidate_link_versions.
        If an existing candidate link with identical idempotency inputs exists, returns it.
        If modifying an existing link_id, increments link_version and creates a new version record.
        """
        data = dict(link)

        left_entity_id = data.get("left_entity_id", "")
        right_entity_id = data.get("right_entity_id", "")
        state = data.get("state", "needs_review")
        score = float(data.get("score", 0.0))
        tier = data.get("tier", "possible_association")
        score_status = data.get("score_status", "calculated")
        score_model_version = data.get("score_model_version", "scoring-v1.0")
        calculation_input_hash = data.get("calculation_input_hash", "")
        conflict_set_id = data.get("conflict_set_id")
        explanation = data.get("explanation")
        changed_by = data.get("changed_by", "system")
        reason = data.get("reason", "Candidate link generation or update")

        # Serialized JSON fields
        cat_breakdown = data.get("category_breakdown_json") or data.get("category_breakdown", {})
        category_breakdown_json = self._serialize_json(cat_breakdown, default_str="{}")

        ev_ids = data.get("evidence_ids_json") or data.get("evidence_ids", [])
        evidence_ids_json = self._serialize_json(ev_ids, default_str="[]")

        competing_ids = data.get("competing_link_ids_json") or data.get("competing_link_ids", [])
        competing_link_ids_json = self._serialize_json(competing_ids, default_str="[]")

        limitations = data.get("limitations_json") or data.get("limitations", [])
        limitations_json = self._serialize_json(limitations, default_str="[]")

        # 1. Check idempotency constraint duplicate
        if calculation_input_hash and score_model_version:
            existing_duplicate = self._find_duplicate(
                left_entity_id=left_entity_id,
                right_entity_id=right_entity_id,
                score_model_version=score_model_version,
                calculation_input_hash=calculation_input_hash,
            )
            if existing_duplicate:
                return existing_duplicate

        # 2. Check if this is an update to an existing link_id or existing pair
        existing_link = None
        if "link_id" in data and data["link_id"]:
            existing_link = self.get_by_id(data["link_id"])

        if not existing_link and left_entity_id and right_entity_id:
            existing_link = self.get_by_pair(left_entity_id, right_entity_id)

        try:
            if existing_link:
                # Update existing link and bump version
                link_id = existing_link["link_id"]
                new_version = int(existing_link.get("link_version", 1)) + 1

                update_sql = """
                UPDATE candidate_links SET
                    link_version = ?,
                    state = ?,
                    score = ?,
                    tier = ?,
                    score_status = ?,
                    category_breakdown_json = ?,
                    evidence_ids_json = ?,
                    conflict_set_id = ?,
                    competing_link_ids_json = ?,
                    explanation = ?,
                    limitations_json = ?,
                    score_model_version = ?,
                    calculation_input_hash = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE link_id = ?
                """
                self.conn.execute(
                    update_sql,
                    (
                        new_version, state, score, tier, score_status,
                        category_breakdown_json, evidence_ids_json, conflict_set_id,
                        competing_link_ids_json, explanation, limitations_json,
                        score_model_version, calculation_input_hash, link_id,
                    ),
                )
            else:
                # Insert new link
                link_id = data.get("link_id") or f"lnk_{uuid.uuid4().hex[:12]}"
                new_version = int(data.get("link_version", 1))

                insert_sql = """
                INSERT INTO candidate_links (
                    link_id, link_version, left_entity_id, right_entity_id,
                    state, score, tier, score_status,
                    category_breakdown_json, evidence_ids_json, conflict_set_id,
                    competing_link_ids_json, explanation, limitations_json,
                    score_model_version, calculation_input_hash
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """
                self.conn.execute(
                    insert_sql,
                    (
                        link_id, new_version, left_entity_id, right_entity_id,
                        state, score, tier, score_status,
                        category_breakdown_json, evidence_ids_json, conflict_set_id,
                        competing_link_ids_json, explanation, limitations_json,
                        score_model_version, calculation_input_hash,
                    ),
                )

            # Insert immutable version record
            version_id = f"ver_{uuid.uuid4().hex[:12]}"
            version_sql = """
            INSERT INTO candidate_link_versions (
                version_id, link_id, link_version, state, score, tier,
                category_breakdown_json, evidence_ids_json, explanation,
                limitations_json, calculation_input_hash, changed_by, reason
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?
            )
            """
            self.conn.execute(
                version_sql,
                (
                    version_id, link_id, new_version, state, score, tier,
                    category_breakdown_json, evidence_ids_json, explanation,
                    limitations_json, calculation_input_hash, changed_by, reason,
                ),
            )

            self.conn.commit()
            return self.get_by_id(link_id)  # type: ignore

        except (sqlite3.IntegrityError, Exception) as exc:
            self.conn.rollback()
            if calculation_input_hash and score_model_version:
                dup = self._find_duplicate(
                    left_entity_id=left_entity_id,
                    right_entity_id=right_entity_id,
                    score_model_version=score_model_version,
                    calculation_input_hash=calculation_input_hash,
                )
                if dup:
                    return dup
            raise exc

    def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for save_candidate_link to conform to BaseRepository interface."""
        return self.save_candidate_link(entity)

    def get_by_pair(self, left_id: str, right_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve candidate link for an entity pair in either direction."""
        query = """
        SELECT * FROM candidate_links
        WHERE (left_entity_id = ? AND right_entity_id = ?)
           OR (left_entity_id = ? AND right_entity_id = ?)
        LIMIT 1
        """
        row = self.conn.fetchone(query, (left_id, right_id, right_id, left_id))
        return self._format_row_for_read(row)

    def get_versions(self, link_id: str) -> List[Dict[str, Any]]:
        """Retrieve historical version records for a candidate link."""
        query = """
        SELECT * FROM candidate_link_versions
        WHERE link_id = ?
        ORDER BY link_version ASC
        """
        rows = self.conn.fetchall(query, (link_id,))
        results = []
        for r in rows:
            if r is not None:
                item = dict(r)
                for col in ("category_breakdown_json", "evidence_ids_json", "limitations_json"):
                    if col in item:
                        item[col] = self._deserialize_json(
                            item[col],
                            default=[] if col.endswith("ids_json") or "limitations" in col else {},
                        )
                results.append(item)
        return results

    def list_by_state(self, state: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List candidate links filtered by state (e.g. 'needs_review', 'confirmed', 'rejected')."""
        query = """
        SELECT * FROM candidate_links
        WHERE state = ?
        ORDER BY score DESC
        LIMIT ? OFFSET ?
        """
        rows = self.conn.fetchall(query, (state, limit, offset))
        return [self._format_row_for_read(r) for r in rows if r is not None]

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List candidate links ordered by score descending."""
        query = f"SELECT * FROM {self.table_name} ORDER BY score DESC LIMIT ? OFFSET ?"
        rows = self.conn.fetchall(query, (limit, offset))
        return [self._format_row_for_read(r) for r in rows if r is not None]
