import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from adapters.base_adapter import BaseAdapter
from analysis.behavior_engine import BehaviorEngine
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

class BehaviorAdapter(BaseAdapter):
    """
    Adapter wrapping behavioral analysis and rebrand correlation results.
    Emits validated EvidenceUnit records (Category B).
    Includes mandatory Category B caps and limitations.
    """

    def __init__(self):
        self.engine = BehaviorEngine()

    def supports(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return any(k in input_data for k in ["posts_a", "posts_b", "migration_analysis", "template_similarity"])

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units: List[EvidenceUnit] = []
        if not self.supports(input_data):
            return units

        actor_a = input_data.get("actor_a") or input_data.get("left_entity_id") or "actor_a"
        actor_b = input_data.get("actor_b") or input_data.get("right_entity_id") or "actor_b"
        linked_pair = sorted([actor_a, actor_b])

        capture_id = input_data.get("capture_id", "cap_behavior_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())

        # If direct posts provided, run engine analysis
        if "posts_a" in input_data and "posts_b" in input_data:
            analysis = self.engine.analyze_migration(
                actor_a=actor_a,
                posts_a=input_data["posts_a"],
                actor_b=actor_b,
                posts_b=input_data["posts_b"]
            )
        else:
            analysis = input_data.get("migration_analysis") or input_data

        if not analysis.get("has_contextual_signal", True) and not analysis.get("is_candidate", False):
            # If contextual signal gate failed, emit zero evidence units (no candidate)
            return units

        # 1. Persona Migration Candidate Evidence
        mig_conf = float(analysis.get("migration_confidence", 0.0))
        if mig_conf > 0.0:
            units.append(self._create_unit(
                indicator_type=IndicatorType.persona_migration_candidate.value,
                indicator_value=f"migration_{linked_pair[0]}_{linked_pair[1]}",
                linked_pair=linked_pair,
                confidence_weight=min(0.85, mig_conf),
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=analysis.get("reason", f"Persona migration candidate proposed between {linked_pair[0]} and {linked_pair[1]}."),
                context_excerpt=f"Matched Phrases: {', '.join(analysis.get('matched_phrases', []))}",
                feature_name="rebrand_migration"
            ))

        # 2. Template Match Evidence
        template_sim = float(analysis.get("template_similarity", 0.0))
        if template_sim >= 0.30:
            units.append(self._create_unit(
                indicator_type=IndicatorType.template_match.value,
                indicator_value=f"template_{hashlib.sha256(str(analysis.get('matched_phrases')).encode()).hexdigest()[:12]}",
                linked_pair=linked_pair,
                confidence_weight=min(0.80, template_sim),
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"High structural template / signature overlap detected ({template_sim:.2f}).",
                context_excerpt=f"Template overlap: {analysis.get('matched_phrases', [])}",
                feature_name="template_match"
            ))

        # 3. Posting Time Pattern Evidence
        time_sim = float(analysis.get("time_similarity", 0.0))
        if time_sim >= 0.50:
            units.append(self._create_unit(
                indicator_type=IndicatorType.posting_time_pattern.value,
                indicator_value=f"time_pattern_24h_utc",
                linked_pair=linked_pair,
                confidence_weight=min(0.70, time_sim),
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"24h UTC posting time activity histogram correlation ({time_sim:.2f}).",
                context_excerpt=f"24h Posting Time Histogram Cosine Similarity: {time_sim:.2f}",
                feature_name="posting_time"
            ))

        # 4. Vocabulary Overlap Evidence
        vocab_sim = float(analysis.get("vocabulary_similarity", 0.0))
        if vocab_sim >= 0.15:
            units.append(self._create_unit(
                indicator_type=IndicatorType.vocabulary_overlap.value,
                indicator_value=f"vocab_overlap_jaccard",
                linked_pair=linked_pair,
                confidence_weight=min(0.65, vocab_sim),
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"Jaccard non-stopword vocabulary overlap detected ({vocab_sim:.2f}).",
                context_excerpt=f"Vocabulary Jaccard Overlap: {vocab_sim:.2f}",
                feature_name="vocabulary"
            ))

        return units

    def _create_unit(
        self,
        indicator_type: str,
        indicator_value: str,
        linked_pair: List[str],
        confidence_weight: float,
        capture_id: str,
        captured_at: str,
        explanation: str,
        context_excerpt: str,
        feature_name: str
    ) -> EvidenceUnit:
        indep_hash = hashlib.sha256(f"{linked_pair[0]}_{linked_pair[1]}_{feature_name}".encode()).hexdigest()[:16]
        indep_group = f"indep_behavior_{feature_name}_{indep_hash}"
        ev_id = f"ev_beh_{hashlib.sha256(f'{indicator_type}_{indicator_value}_{linked_pair[0]}_{linked_pair[1]}'.encode()).hexdigest()[:12]}"

        return EvidenceUnit(
            evidence_id=ev_id,
            schema_version="1.0.0",
            category="B",
            capture_id=capture_id,
            source="behavior_engine",
            source_version="1.0.0",
            indicator_type=indicator_type,
            indicator_value=indicator_value,
            indicator_role=None,
            linked_entities=linked_pair,
            confidence_weight=round(confidence_weight, 2),
            source_reliability=0.85,
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=None,
            captured_at=captured_at,
            time_confidence=1.0,
            source_url="internal://analysis/behavior",
            raw_evidence_hash=hashlib.sha256(indicator_value.encode()).hexdigest(),
            raw_evidence_reference="fixtures/market-a/ghostvendor.html",
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=explanation,
            limitations=[
                "Behavioral and writing-style similarity alone cannot reach Likely Same Actor or higher tiers without cryptographic/technical corroboration.",
                "Category B maximum contribution capped at possible_association threshold (0.65)."
            ],
            context_excerpt=context_excerpt,
            model_metadata={"feature_name": feature_name, "raw_weight": confidence_weight}
        )
