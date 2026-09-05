"""
ExplainableFusionEngine Module.
Multi-category explainable probabilistic fusion engine for dark-web threat actor attribution.
Enforces K/I/B/S category caps, Noisy-OR combination, boundary hysteresis (EC-25),
and cryptographic calculation input hashes.
"""

import hashlib
import os
import yaml
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from models.candidate_link import CandidateLink
from models.enums import LinkState, ScoreStatus, Tier
from models.evidence import EvidenceUnit
from fusion.category_classifier import CategoryClassifier
from fusion.explanation_builder import ExplanationBuilder


class ExplainableFusionEngine:
    """
    Multi-category explainable fusion engine:
      - Classifies evidence into K, I, B, S categories
      - Computes Noisy-OR per category for unique independence_group_ids (EC-24)
      - Applies Category S cap (S contribution <= 0.20)
      - Applies Category I and B caps (single category <= 0.70 possible_association)
      - Calculates final fused score across categories
      - Maps final score to Tier with boundary hysteresis margin (+-0.03) (EC-25)
      - Generates deterministic calculation_input_hash
      - Produces validated CandidateLink objects
    """

    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "scoring.yaml")

        self.score_model_version = "scoring-v1.0"
        self.hysteresis_margin = 0.03
        self.categories_config = {
            "K": {"name": "Cryptographic & Hard Identifiers", "weight": 1.00, "max_contribution": 1.00},
            "I": {"name": "Infrastructure", "weight": 0.85, "max_contribution": 0.65},
            "B": {"name": "Behavioral", "weight": 0.80, "max_contribution": 0.65},
            "S": {"name": "Semantic & Stylometric", "weight": 0.70, "max_contribution": 0.20},
        }
        self.tiers_config = {
            "insufficient_evidence": {"min_score": 0.00, "max_score": 0.20},
            "unresolved": {"min_score": 0.20, "max_score": 0.40},
            "possible_association": {"min_score": 0.40, "max_score": 0.70},
            "likely_same_actor": {"min_score": 0.70, "max_score": 0.90},
            "observed_technical_identity": {"min_score": 0.90, "max_score": 1.00},
        }

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.score_model_version = data.get("score_model_version", self.score_model_version)
                self.hysteresis_margin = float(data.get("hysteresis_margin", self.hysteresis_margin))
                if "categories" in data:
                    self.categories_config = data["categories"]
                if "tiers" in data:
                    self.tiers_config = data["tiers"]

    @staticmethod
    def calculate_noisy_or(weights: List[float]) -> float:
        """
        Computes standard Noisy-OR combination: P = 1 - prod(1 - w_i).
        Clamps weights to [0.0, 1.0] and rounds result to 4 decimal places.
        """
        if not weights:
            return 0.0
        product = 1.0
        for w in weights:
            clamped_w = max(0.0, min(1.0, float(w)))
            product *= (1.0 - clamped_w)
        return round(1.0 - product, 4)

    def compute_calculation_input_hash(self, evidence_ids: List[str]) -> str:
        """
        Computes deterministic calculation_input_hash:
        SHA-256 of sorted evidence IDs prefixed by score model version.
        """
        sorted_ids = sorted(str(eid) for eid in evidence_ids)
        input_str = f"{self.score_model_version}:" + ",".join(sorted_ids)
        digest = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _raw_tier_mapping(self, score: float) -> str:
        """
        Maps a score directly to its tier without applying hysteresis.
        """
        if score < self.tiers_config.get("insufficient_evidence", {}).get("max_score", 0.20):
            return Tier.insufficient_evidence.value
        elif score < self.tiers_config.get("unresolved", {}).get("max_score", 0.40):
            return Tier.unresolved.value
        elif score < self.tiers_config.get("possible_association", {}).get("max_score", 0.70):
            return Tier.possible_association.value
        elif score < self.tiers_config.get("likely_same_actor", {}).get("max_score", 0.90):
            return Tier.likely_same_actor.value
        else:
            return Tier.observed_technical_identity.value

    def map_score_to_tier(
        self,
        score: float,
        previous_link: Optional[Union[CandidateLink, Dict[str, Any]]] = None,
    ) -> str:
        """
        Maps score to Tier string, applying hysteresis margin (+-0.03)
        when a previous link is provided to eliminate boundary flicker (EC-25).
        """
        raw_tier = self._raw_tier_mapping(score)
        if previous_link is None:
            return raw_tier

        prev_score = getattr(previous_link, "score", None)
        if prev_score is None and isinstance(previous_link, dict):
            prev_score = previous_link.get("score")

        prev_tier = getattr(previous_link, "tier", None)
        if prev_tier is None and isinstance(previous_link, dict):
            prev_tier = previous_link.get("tier")

        if prev_score is not None and prev_tier is not None:
            if round(abs(score - float(prev_score)), 6) <= self.hysteresis_margin:
                return str(prev_tier)

        return raw_tier

    def evaluate_pair(
        self,
        left_entity_id: str,
        right_entity_id: str,
        evidence_units: List[Union[EvidenceUnit, Dict[str, Any]]],
        previous_link: Optional[Union[CandidateLink, Dict[str, Any]]] = None,
    ) -> CandidateLink:
        """
        Evaluates an entity pair across all supplied evidence units.
        Performs category grouping, Noisy-OR fusion, cap enforcement, tier mapping,
        and generates a CandidateLink.
        """
        # Canonical entity ordering (alphabetical)
        left = min(str(left_entity_id), str(right_entity_id))
        right = max(str(left_entity_id), str(right_entity_id))

        # 1. Group evidence by Category & Independence Group
        cat_evidence: Dict[str, Dict[str, float]] = {"K": {}, "I": {}, "B": {}, "S": {}}
        cat_ev_ids: Dict[str, List[str]] = {"K": [], "I": [], "B": [], "S": []}
        all_ev_ids: List[str] = []

        for u in evidence_units:
            cat = CategoryClassifier.classify(u)
            if cat not in cat_evidence:
                cat = "K"

            ev_id = getattr(u, "evidence_id", None)
            if ev_id is None and isinstance(u, dict):
                ev_id = u.get("evidence_id", "")
            if ev_id:
                all_ev_ids.append(str(ev_id))
                cat_ev_ids[cat].append(str(ev_id))

            grp = getattr(u, "independence_group_id", None)
            if grp is None and isinstance(u, dict):
                grp = u.get("independence_group_id", ev_id)
            grp_key = str(grp or ev_id or len(all_ev_ids))

            weight = getattr(u, "confidence_weight", None)
            if weight is None and isinstance(u, dict):
                weight = u.get("confidence_weight", 0.0)
            weight_val = float(weight or 0.0)

            # Deduplicate by max weight within same independence_group_id (EC-24)
            current_max = cat_evidence[cat].get(grp_key, 0.0)
            if weight_val > current_max:
                cat_evidence[cat][grp_key] = weight_val

        # 2. Calculate category scores using Noisy-OR per category
        cat_scores: Dict[str, float] = {}
        category_breakdown: Dict[str, Any] = {}

        for cat in ["K", "I", "B", "S"]:
            weights = list(cat_evidence[cat].values())
            raw_cat_score = self.calculate_noisy_or(weights)
            max_cap = float(self.categories_config.get(cat, {}).get("max_contribution", 1.0))
            capped_score = min(raw_cat_score, max_cap)
            cat_scores[cat] = capped_score

            category_breakdown[cat] = {
                "score": round(capped_score, 4),
                "state": "observed" if weights else "not_available",
                "evidence_ids": cat_ev_ids[cat],
            }

        # 3. Overall Fusion Score calculation across categories
        k_score = cat_scores["K"]
        i_score = cat_scores["I"]
        b_score = cat_scores["B"]
        s_score = cat_scores["S"]

        # Noisy-OR across active categories
        active_cat_scores = [s for s in [k_score, i_score, b_score, s_score] if s > 0]
        raw_fused = self.calculate_noisy_or(active_cat_scores)

        # Enforce Category S cap (S contribution <= 0.20 to overall score)
        score_without_s = self.calculate_noisy_or([s for s in [k_score, i_score, b_score] if s > 0])
        s_cap = float(self.categories_config.get("S", {}).get("max_contribution", 0.20))
        if raw_fused - score_without_s > s_cap:
            final_score = score_without_s + s_cap
        else:
            final_score = raw_fused

        # Enforce Category I and B caps (single category alone cannot exceed possible_association threshold 0.70)
        active_cats = [c for c in ["K", "I", "B", "S"] if cat_scores[c] > 0]
        if len(active_cats) == 1:
            lone_cat = active_cats[0]
            if lone_cat in ("I", "B"):
                max_contribution = float(self.categories_config.get(lone_cat, {}).get("max_contribution", 0.65))
                final_score = min(final_score, 0.70, max_contribution)
            elif lone_cat == "S":
                final_score = min(final_score, s_cap)

        # Text-only corroboration cap (B + S without hard identifiers K or infrastructure I)
        if k_score == 0 and i_score == 0:
            final_score = min(final_score, 0.65)

        final_score = round(max(0.0, min(1.0, final_score)), 4)

        # 4. Map Score to Tier with Hysteresis (EC-25)
        tier = self.map_score_to_tier(final_score, previous_link=previous_link)

        # 5. Calculation Input Hash (SHA-256 of sorted evidence IDs + model version)
        calc_hash = self.compute_calculation_input_hash(all_ev_ids)

        # 6. Explanation & Limitations
        explanation, limitations = ExplanationBuilder.build_explanation(
            evidence_units=evidence_units,
            category_breakdown=category_breakdown,
            tier=tier,
            score=final_score,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_link_id = getattr(previous_link, "link_id", None) if previous_link else None
        if not prev_link_id and isinstance(previous_link, dict):
            prev_link_id = previous_link.get("link_id")

        link_id = prev_link_id or f"lnk_{hashlib.sha256(f'{left}_{right}'.encode()).hexdigest()[:12]}"

        prev_version = getattr(previous_link, "link_version", None) if previous_link else None
        if prev_version is None and isinstance(previous_link, dict):
            prev_version = previous_link.get("link_version")
        version = (int(prev_version) + 1) if prev_version is not None else 1

        prev_state = getattr(previous_link, "state", None) if previous_link else None
        if prev_state is None and isinstance(previous_link, dict):
            prev_state = previous_link.get("state")

        prev_created = getattr(previous_link, "created_at", None) if previous_link else None
        if prev_created is None and isinstance(previous_link, dict):
            prev_created = previous_link.get("created_at")

        return CandidateLink(
            link_id=link_id,
            link_version=version,
            left_entity_id=left,
            right_entity_id=right,
            state=prev_state or LinkState.proposed.value,
            score=final_score,
            tier=tier,
            score_status=ScoreStatus.observed.value if evidence_units else ScoreStatus.insufficient.value,
            category_breakdown=category_breakdown,
            evidence_ids=sorted(list(set(all_ev_ids))),
            explanation=explanation,
            limitations=limitations,
            score_model_version=self.score_model_version,
            calculation_input_hash=calc_hash,
            created_at=prev_created or now_iso,
            updated_at=now_iso,
        )
