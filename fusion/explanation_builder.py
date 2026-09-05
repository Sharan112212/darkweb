"""
ExplanationBuilder Module.
Generates deterministic human-readable analyst explanations and aggregates caveats/limitations
across all contributing EvidenceUnit records.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from models.evidence import EvidenceUnit


class ExplanationBuilder:
    """
    Generates deterministic human-readable analyst explanations summarizing contributing
    K, I, B, S categories, and aggregates limitations across contributing EvidenceUnit records
    without duplication.
    """

    CATEGORY_NAMES = {
        "K": "Cryptographic & Hard Identifiers",
        "I": "Infrastructure",
        "B": "Behavioral",
        "S": "Semantic & Stylometric",
    }

    @classmethod
    def build_explanation(
        cls,
        evidence_units: List[Union[EvidenceUnit, Dict[str, Any]]],
        category_breakdown: Dict[str, Any],
        tier: str,
        score: float,
    ) -> Tuple[str, List[str]]:
        """
        Builds both the deterministic explanation text and the deduplicated limitations list.

        Args:
            evidence_units: List of contributing evidence units.
            category_breakdown: Mapping of category codes to score, state, and evidence_ids.
            tier: Assigned tier string.
            score: Final fused score.

        Returns:
            Tuple of (explanation_text, list_of_limitations)
        """
        explanation = cls.build_text_explanation(evidence_units, category_breakdown, tier, score)
        limitations = cls.build_limitations(evidence_units, category_breakdown)
        return explanation, limitations

    @classmethod
    def build_text_explanation(
        cls,
        evidence_units: List[Union[EvidenceUnit, Dict[str, Any]]],
        category_breakdown: Dict[str, Any],
        tier: str,
        score: float,
    ) -> str:
        """
        Constructs deterministic, human-readable analyst summary text.
        """
        if not evidence_units:
            return f"Candidate link evaluated at tier '{tier}' (score: {score:.2f}). No contributing evidence units available."

        active_categories = []
        cat_details = []

        for cat_code in ["K", "I", "B", "S"]:
            info = category_breakdown.get(cat_code, {})
            cat_score = float(info.get("score", 0.0))
            cat_state = info.get("state", "not_available")
            ev_ids = info.get("evidence_ids", [])

            if cat_state == "observed" and ev_ids:
                cat_name = cls.CATEGORY_NAMES.get(cat_code, cat_code)
                active_categories.append(f"{cat_code} ({cat_name})")
                cat_details.append(f"[{cat_code}] {cat_name}: score {cat_score:.2f} ({len(ev_ids)} unit(s))")

        if active_categories:
            cats_summary = ", ".join(active_categories)
            details_str = "; ".join(cat_details)
            explanation = (
                f"Candidate correlation evaluated at tier '{tier}' with fused score {score:.2f}. "
                f"Contributing categories: {cats_summary}. Breakdown: {details_str}. "
                f"Total evidence units evaluated: {len(evidence_units)}."
            )
        else:
            explanation = (
                f"Candidate correlation evaluated at tier '{tier}' with fused score {score:.2f}. "
                f"Total evidence units evaluated: {len(evidence_units)}."
            )

        return explanation

    @classmethod
    def build_limitations(
        cls,
        evidence_units: List[Union[EvidenceUnit, Dict[str, Any]]],
        category_breakdown: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Aggregates all limitations across contributing evidence units without duplication.
        Preserves original insertion order while enforcing uniqueness.
        """
        seen = set()
        deduped_limitations: List[str] = []

        for unit in evidence_units:
            limits = getattr(unit, "limitations", None)
            if limits is None and isinstance(unit, dict):
                limits = unit.get("limitations", [])

            if isinstance(limits, list):
                for item in limits:
                    cleaned = str(item).strip()
                    if cleaned and cleaned not in seen:
                        seen.add(cleaned)
                        deduped_limitations.append(cleaned)

        # Contextual methodology caveats based on observed categories
        if category_breakdown:
            s_info = category_breakdown.get("S", {})
            if s_info.get("state") == "observed" and s_info.get("score", 0.0) > 0:
                s_caveat = "Semantic and stylometric similarity is supporting evidence only, not standalone proof of identity."
                if s_caveat not in seen:
                    seen.add(s_caveat)
                    deduped_limitations.append(s_caveat)

            i_info = category_breakdown.get("I", {})
            k_info = category_breakdown.get("K", {})
            if (
                i_info.get("state") == "observed"
                and i_info.get("score", 0.0) > 0
                and k_info.get("score", 0.0) == 0
            ):
                i_caveat = "Infrastructure matches may reflect shared hosting, CDN, or multi-tenant proxies."
                if i_caveat not in seen:
                    seen.add(i_caveat)
                    deduped_limitations.append(i_caveat)

        if not deduped_limitations:
            deduped_limitations.append("All technical observations subject to analyst review.")

        return deduped_limitations
