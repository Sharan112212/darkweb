from typing import List, Tuple
from models.evidence import EvidenceUnit
from models.enums import IndicatorType

class LegacyFusionAdapter:
    """
    Bridge adapter converting new canonical EvidenceUnit records back into legacy
    SQLite relationship_links format (actor_a, actor_b, link_type, evidence, confidence_score)
    so existing fusion.py continues working seamlessly until Branch 3.
    """

    @staticmethod
    def to_legacy_link(evidence_unit: EvidenceUnit) -> Tuple[str, str, str, str, int]:
        left = min(evidence_unit.linked_entities[0], evidence_unit.linked_entities[1])
        right = max(evidence_unit.linked_entities[0], evidence_unit.linked_entities[1])

        if evidence_unit.indicator_type in (IndicatorType.pgp_fingerprint.value, IndicatorType.wallet_address.value):
            link_type = "shared_identifier"
        elif evidence_unit.indicator_type == IndicatorType.semantic_similarity.value:
            link_type = "stylometric"
        else:
            link_type = "infrastructure_match"

        confidence_score = int(round(evidence_unit.confidence_weight * 100))
        return (left, right, link_type, evidence_unit.explanation, confidence_score)

    @classmethod
    def to_legacy_dict(cls, evidence_unit: EvidenceUnit) -> dict:
        tup = cls.to_legacy_link(evidence_unit)
        return {
            "actor_a": tup[0],
            "actor_b": tup[1],
            "link_type": tup[2],
            "evidence": tup[3],
            "confidence_score": tup[4],
        }

    @classmethod
    def write_to_db(cls, evidence_units: List[EvidenceUnit], db_path: str = "darkweb_intel.db"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationship_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_a TEXT,
                actor_b TEXT,
                link_type TEXT,
                evidence TEXT,
                confidence_score REAL
            )
        """)
        for unit in evidence_units:
            tup = cls.to_legacy_link(unit)
            cur.execute("""
                INSERT INTO relationship_links (actor_a, actor_b, link_type, evidence, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            """, tup)
        conn.commit()
        conn.close()
