import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from adapters.base_adapter import BaseAdapter
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

class InfraEvidenceAdapter(BaseAdapter):
    """
    Adapter wrapping x509 TLS certificate fingerprint correlations
    (from infra-matcher/match_infra.py). Emits validated EvidenceUnit records (Category I).
    """

    def supports(self, input_data: Any) -> bool:
        return isinstance(input_data, dict) and "onion_address" in input_data and "clearnet_host" in input_data

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units = []
        onion = input_data.get("onion_address", "").strip().lower()
        clearnet = input_data.get("clearnet_host", "").strip().lower()
        raw_evidence = input_data.get("evidence", "")
        capture_id = input_data.get("capture_id", "cap_infra_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())

        if not onion or not clearnet:
            return units

        cert_fingerprint = self.normalize_fingerprint(raw_evidence)
        left_entity = f"onion_{onion}"
        right_entity = f"clearnet_{clearnet}"
        linked_pair = sorted([left_entity, right_entity])

        # Dynamic confidence calculation: Freshness (0.9) x Rarity (0.8)
        freshness_factor = float(input_data.get("freshness", 0.90))
        rarity_factor = float(input_data.get("rarity", 0.85))
        confidence = round(freshness_factor * rarity_factor, 2)

        indep_group = f"indep_cert_{hashlib.sha256(cert_fingerprint.encode()).hexdigest()[:16]}"

        units.append(EvidenceUnit(
            evidence_id=f"ev_cert_{hashlib.sha256(f'{onion}_{clearnet}_{cert_fingerprint}'.encode()).hexdigest()[:12]}",
            schema_version="1.0.0",
            category="I",
            capture_id=capture_id,
            source="infra_matcher",
            source_version="1.0.0",
            indicator_type=IndicatorType.certificate_fingerprint.value,
            indicator_value=cert_fingerprint,
            indicator_role=None,
            linked_entities=linked_pair,
            confidence_weight=confidence,
            source_reliability=0.95,
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=input_data.get("matched_at"),
            captured_at=captured_at,
            time_confidence=1.0,
            source_url=f"tls://{onion}:443",
            raw_evidence_hash=hashlib.sha256(raw_evidence.encode()).hexdigest(),
            raw_evidence_reference=input_data.get("raw_reference", "certs/shared_cert.pem"),
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=f"Exact TLS certificate SHA-256 fingerprint match between {onion} and {clearnet} ({cert_fingerprint[:16]}...).",
            limitations=[
                "Shared certificate may reflect shared hosting or CDN infrastructure, not operator identity.",
                "Infrastructure evidence alone cannot exceed Possible Association tier."
            ],
            context_excerpt=f"SHA-256 Certificate Fingerprint: {cert_fingerprint}",
            model_metadata={"freshness": freshness_factor, "rarity": rarity_factor}
        ))

        return units

    @staticmethod
    def normalize_fingerprint(evidence_str: str) -> str:
        if "SHA-256:" in evidence_str:
            evidence_str = evidence_str.split("SHA-256:")[1].strip()
        cleaned = evidence_str.replace(":", "").replace(" ", "").lower()
        return cleaned
