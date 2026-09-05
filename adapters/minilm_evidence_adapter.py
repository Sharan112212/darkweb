import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from adapters.base_adapter import BaseAdapter
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

class MiniLMEvidenceAdapter(BaseAdapter):
    """
    Adapter wrapping SBERT SentenceTransformer cosine similarity results
    (from stylometry.py). Emits validated EvidenceUnit records (Category S).
    """

    def supports(self, input_data: Any) -> bool:
        return isinstance(input_data, dict) and "actor_a" in input_data and "actor_b" in input_data and "similarity" in input_data

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units = []
        actor_a = input_data.get("actor_a", "").strip()
        actor_b = input_data.get("actor_b", "").strip()
        similarity = float(input_data.get("similarity", 0.0))
        capture_id = input_data.get("capture_id", "cap_minilm_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())

        if not actor_a or not actor_b or similarity < 0.75:
            return units

        left_entity = min(actor_a, actor_b)
        right_entity = max(actor_a, actor_b)
        linked_pair = [left_entity, right_entity]

        # Apply corpus quality gates: check post count and char count
        post_count_a = input_data.get("post_count_a", 5)
        post_count_b = input_data.get("post_count_b", 5)
        char_count_a = input_data.get("char_count_a", 1500)
        char_count_b = input_data.get("char_count_b", 1500)

        # Gate enforcement: minimum 5 posts and 1500 cleaned characters per corpus
        if post_count_a < 5 or post_count_b < 5 or char_count_a < 1500 or char_count_b < 1500:
            return units

        corpus_hash_a = hashlib.sha256(f"{left_entity}_{post_count_a}_{char_count_a}".encode()).hexdigest()[:12]
        corpus_hash_b = hashlib.sha256(f"{right_entity}_{post_count_b}_{char_count_b}".encode()).hexdigest()[:12]
        corpus_hash = f"{corpus_hash_a}_{corpus_hash_b}"

        indep_group = f"indep_minilm_{left_entity}_{right_entity}"

        # Category S score contribution cap: similarity scaled
        confidence = round(similarity * 0.85, 2)

        units.append(EvidenceUnit(
            evidence_id=f"ev_minilm_{hashlib.sha256(f'{left_entity}_{right_entity}_{corpus_hash}'.encode()).hexdigest()[:12]}",
            schema_version="1.0.0",
            category="S",
            capture_id=capture_id,
            source="minilm_stylometry",
            source_version="all-MiniLM-L6-v2",
            indicator_type=IndicatorType.semantic_similarity.value,
            indicator_value=f"similarity_{similarity:.4f}",
            indicator_role=None,
            linked_entities=linked_pair,
            confidence_weight=confidence,
            source_reliability=0.90,
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=None,
            captured_at=captured_at,
            time_confidence=1.0,
            source_url=f"semantic://{left_entity}/{right_entity}",
            raw_evidence_hash=corpus_hash,
            raw_evidence_reference="models/all-MiniLM-L6-v2/",
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=f"SBERT semantic similarity match between {left_entity} and {right_entity} (cosine similarity: {similarity:.4f}).",
            limitations=[
                "Semantic similarity is supporting evidence only, not authorship proof.",
                "Text-only signals cannot yield Likely Same Actor or Observed Technical Identity without non-text corroboration."
            ],
            context_excerpt=f"Sentence-BERT Cosine Similarity: {similarity:.4f}",
            model_metadata={
                "model_name": "all-MiniLM-L6-v2",
                "similarity": similarity,
                "post_counts": [post_count_a, post_count_b],
                "char_counts": [char_count_a, char_count_b]
            }
        ))

        return units
