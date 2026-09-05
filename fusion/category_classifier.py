"""
CategoryClassifier Module.
Maps an EvidenceUnit into its indicator category code (K, I, B, S)
according to SIH26151 Frozen Data Contracts.
"""

from typing import Any, Union
from models.evidence import EvidenceUnit
from models.enums import IndicatorType


class CategoryClassifier:
    """
    Classifies an EvidenceUnit or raw indicator_type string into its canonical category:
      - K: Cryptographic & Hard Identifiers
      - I: Infrastructure
      - B: Behavioral
      - S: Semantic & Stylometric
    """

    K_TYPES = {
        IndicatorType.pgp_fingerprint.value,
        IndicatorType.wallet_address.value,
        IndicatorType.alias.value,
        IndicatorType.contact_identifier.value,
    }

    I_TYPES = {
        IndicatorType.certificate_fingerprint.value,
        IndicatorType.infrastructure_match.value,
        IndicatorType.onionscan_analytics_id.value,
        IndicatorType.onionscan_exif_leak.value,
        IndicatorType.onionscan_server_status.value,
        IndicatorType.onionscan_ssh_key.value,
        IndicatorType.onionscan_certificate.value,
        IndicatorType.onionscan_open_directory.value,
    }

    B_TYPES = {
        IndicatorType.posting_time_pattern.value,
        IndicatorType.vocabulary_overlap.value,
        IndicatorType.template_match.value,
        IndicatorType.persona_migration_candidate.value,
    }

    S_TYPES = {
        IndicatorType.semantic_similarity.value,
        IndicatorType.classical_stylometry.value,
    }

    @classmethod
    def classify_type(cls, indicator_type: Union[str, IndicatorType]) -> str:
        """
        Classifies an indicator type name or enum into a category code ('K', 'I', 'B', 'S').
        """
        if isinstance(indicator_type, IndicatorType):
            itype = indicator_type.value
        else:
            itype = str(indicator_type).strip().lower()

        if itype in cls.K_TYPES:
            return "K"
        if itype in cls.I_TYPES or itype.startswith("onionscan_"):
            return "I"
        if itype in cls.B_TYPES:
            return "B"
        if itype in cls.S_TYPES:
            return "S"
        return "K"

    @classmethod
    def classify(cls, evidence_unit: Union[EvidenceUnit, dict, Any]) -> str:
        """
        Classifies an EvidenceUnit into its category code ('K', 'I', 'B', 'S').
        """
        itype = getattr(evidence_unit, "indicator_type", None)
        if itype is None and isinstance(evidence_unit, dict):
            itype = evidence_unit.get("indicator_type")

        if itype:
            return cls.classify_type(itype)

        # Fallback to pre-existing category field if valid
        cat = getattr(evidence_unit, "category", None)
        if cat is None and isinstance(evidence_unit, dict):
            cat = evidence_unit.get("category")
        if cat in {"K", "I", "B", "S"}:
            return cat

        return "K"
