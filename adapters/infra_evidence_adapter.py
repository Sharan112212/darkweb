import math
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from adapters.base_adapter import BaseAdapter
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

class InfraEvidenceAdapter(BaseAdapter):
    """
    Adapter wrapping infrastructure correlation signals (TLS certificate fingerprints,
    OnionScan indicators, IP/host co-location).
    Emits validated EvidenceUnit records (Category I).
    Includes freshness decay calculation and EC-08 shared hosting caveats.
    """

    DEFAULT_BASE_WEIGHTS = {
        IndicatorType.certificate_fingerprint.value: 0.80,
        IndicatorType.infrastructure_match.value: 0.70,
        IndicatorType.onionscan_analytics_id.value: 0.85,
        IndicatorType.onionscan_exif_leak.value: 0.75,
        IndicatorType.onionscan_server_status.value: 0.65,
        IndicatorType.onionscan_ssh_key.value: 0.60,
        IndicatorType.onionscan_certificate.value: 0.50,
        IndicatorType.onionscan_open_directory.value: 0.40,
    }

    def supports(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return any(k in input_data for k in ["onion_address", "clearnet_host", "indicator_type", "certificate_fingerprint"])

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units: List[EvidenceUnit] = []
        if not self.supports(input_data):
            return units

        indicator_type = input_data.get("indicator_type", IndicatorType.certificate_fingerprint.value)
        
        onion = input_data.get("onion_address", "").strip().lower()
        clearnet = input_data.get("clearnet_host", "").strip().lower()
        left_entity = input_data.get("left_entity_id") or (f"onion_{onion}" if onion else "entity_a")
        right_entity = input_data.get("right_entity_id") or (f"clearnet_{clearnet}" if clearnet else "entity_b")
        linked_pair = sorted([left_entity, right_entity])

        raw_evidence = input_data.get("evidence") or input_data.get("certificate_fingerprint") or input_data.get("indicator_value") or ""
        cert_fingerprint = self.normalize_fingerprint(str(raw_evidence))

        capture_id = input_data.get("capture_id", "cap_infra_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())
        observation_date = input_data.get("matched_at") or input_data.get("observation_date")

        # Compute Freshness Decay & Rarity Factor (EC-08)
        rarity_factor = float(input_data.get("rarity", 0.85))

        if "freshness" in input_data:
            freshness_factor = float(input_data["freshness"])
        else:
            freshness_factor = self.calculate_freshness(observation_date or captured_at)

        if "base_weight" in input_data:
            base_weight = float(input_data["base_weight"])
            confidence = round(base_weight * freshness_factor * rarity_factor, 2)
        elif "freshness" in input_data:
            # Legacy format support: direct product of freshness x rarity
            confidence = round(freshness_factor * rarity_factor, 2)
            base_weight = 1.0
        else:
            base_weight = self.DEFAULT_BASE_WEIGHTS.get(indicator_type, 0.60)
            confidence = round(base_weight * freshness_factor * rarity_factor, 2)

        confidence = max(0.05, min(1.0, confidence))

        indep_group = input_data.get("independence_group_id") or f"indep_infra_{hashlib.sha256(cert_fingerprint.encode()).hexdigest()[:16]}"

        units.append(EvidenceUnit(
            evidence_id=f"ev_infra_{hashlib.sha256(f'{linked_pair[0]}_{linked_pair[1]}_{cert_fingerprint}_{indicator_type}'.encode()).hexdigest()[:12]}",
            schema_version="1.0.0",
            category="I",
            capture_id=capture_id,
            source=input_data.get("source", "infra_matcher"),
            source_version="1.0.0",
            indicator_type=indicator_type,
            indicator_value=cert_fingerprint,
            indicator_role=input_data.get("indicator_role"),
            linked_entities=linked_pair,
            confidence_weight=confidence,
            source_reliability=float(input_data.get("source_reliability", 0.90)),
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=observation_date,
            captured_at=captured_at,
            time_confidence=1.0,
            source_url=input_data.get("source_url", f"tls://{onion if onion else 'host'}:443"),
            raw_evidence_hash=hashlib.sha256(cert_fingerprint.encode()).hexdigest(),
            raw_evidence_reference=input_data.get("raw_reference", "certs/shared_cert.pem"),
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=input_data.get("explanation", f"Infrastructure correlation ({indicator_type}) matching between {linked_pair[0]} and {linked_pair[1]}."),
            limitations=[
                "Shared certificate or infrastructure may reflect shared hosting provider, reverse proxy, or CDN rather than operator identity (EC-08).",
                "Infrastructure evidence alone cannot exceed Possible Association tier (Category I max contribution 0.65)."
            ],
            context_excerpt=input_data.get("context_excerpt", f"Infrastructure Match: {cert_fingerprint}"),
            model_metadata={
                "base_weight": base_weight,
                "freshness_factor": freshness_factor,
                "rarity_factor": rarity_factor,
                "decay_applied": freshness_factor < 1.0
            }
        ))

        return units

    @staticmethod
    def normalize_fingerprint(evidence_str: str) -> str:
        """Normalizes hex fingerprints or indicator values."""
        if "SHA-256:" in evidence_str:
            evidence_str = evidence_str.split("SHA-256:")[1].strip()
        cleaned = evidence_str.replace(":", "").replace(" ", "").lower()
        return cleaned

    @staticmethod
    def calculate_freshness(observation_date_str: str, half_life_days: float = 180.0) -> float:
        """
        Calculates exponential decay factor based on age of observation.
        Freshness = exp(-ln(2) * (days_old / half_life_days))
        Minimum threshold: 0.20.
        """
        try:
            if not observation_date_str:
                return 1.0
            obs_dt = datetime.fromisoformat(observation_date_str.replace("Z", "+00:00"))
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            age_days = (now_dt - obs_dt).total_seconds() / 86400.0
            if age_days <= 0:
                return 1.0
            decay = math.exp(-math.log(2) * (age_days / half_life_days))
            return max(0.20, round(decay, 4))
        except Exception:
            return 1.0
