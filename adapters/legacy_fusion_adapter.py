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
