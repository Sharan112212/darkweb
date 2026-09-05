import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from adapters.base_adapter import BaseAdapter
from analysis.classical_stylometry import ClassicalStylometryEngine
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

class ClassicalStylometryAdapter(BaseAdapter):
    """
    Adapter wrapping ClassicalStylometryEngine.
    Emits validated EvidenceUnit records (Category S).
    Strictly caps total contribution at 0.20 per EC-20 / Build Guide §14.
    Appends limitation: ["Classical stylometry is supporting evidence only, capped at 0.20 contribution"].
    """

    def __init__(self):
        self.engine = ClassicalStylometryEngine()

    def supports(self, input_data: Any) -> bool:
        return isinstance(input_data, dict) and "posts_a" in input_data and "posts_b" in input_data

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units: List[EvidenceUnit] = []
        if not self.supports(input_data):
            return units

        actor_a = input_data.get("actor_a") or input_data.get("left_entity_id") or "actor_a"
        actor_b = input_data.get("actor_b") or input_data.get("right_entity_id") or "actor_b"
        linked_pair = sorted([actor_a, actor_b])

        capture_id = input_data.get("capture_id", "cap_stylometry_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())

        posts_a = input_data["posts_a"]
        posts_b = input_data["posts_b"]

        result = self.engine.analyze_pair(posts_a, posts_b)

        # Gate failure check per EC-19: emit NO evidence units if gates fail
        if not result.get("is_eligible", False):
            return units

        similarity = float(result.get("similarity", 0.0))

        # We only emit evidence if there is meaningful similarity (>= 0.40)
        if similarity < 0.40:
            return units

        # Category S score cap: raw confidence weight capped to 0.20 contribution
        confidence_weight = round(min(0.20, similarity * 0.20), 2)
        corpus_hash = result.get("corpus_hash", "hash_unknown")

        indep_group = f"indep_classical_stylometry_{linked_pair[0]}_{linked_pair[1]}"
        ev_id = f"ev_style_{hashlib.sha256(f'{linked_pair[0]}_{linked_pair[1]}_{corpus_hash}'.encode()).hexdigest()[:12]}"

        units.append(EvidenceUnit(
            evidence_id=ev_id,
            schema_version="1.0.0",
            category="S",
            capture_id=capture_id,
            source="classical_stylometry_engine",
            source_version="1.0.0",
            indicator_type=IndicatorType.classical_stylometry.value,
            indicator_value=f"similarity_{similarity:.4f}",
            indicator_role=None,
            linked_entities=linked_pair,
            confidence_weight=confidence_weight,
            source_reliability=0.80,
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=None,
            captured_at=captured_at,
            time_confidence=1.0,
            source_url="internal://analysis/classical_stylometry",
            raw_evidence_hash=corpus_hash,
            raw_evidence_reference="analysis/classical_stylometry.py",
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=f"Classical stylometric feature overlap (function words, sentence structure, punctuation, n-grams) cosine similarity: {similarity:.4f}.",
            limitations=[
                "Classical stylometry is supporting evidence only, capped at 0.20 contribution.",
                "Text-only signals cannot yield Likely Same Actor or Observed Technical Identity without non-text corroboration."
            ],
            context_excerpt=f"Function-word and n-gram Cosine Similarity: {similarity:.4f}",
            model_metadata={
                "feature_name": "classical_stylometry",
                "similarity": similarity,
                "corpus_hash": corpus_hash,
                "char_counts": [result.get("cleaned_char_count_a"), result.get("cleaned_char_count_b")],
                "post_counts": [len(posts_a), len(posts_b)],
                "language": "en"
            }
        ))

        return units
