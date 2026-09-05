import hashlib
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from adapters.base_adapter import BaseAdapter
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, IndicatorRole, ProcessingStatus

class IdentityEvidenceAdapter(BaseAdapter):
    """
    Adapter wrapping PGP, Cryptocurrency Wallet, and Alias identity correlations
    (from identity_graph.py). Emits validated EvidenceUnit records (Category K).
    """

    def supports(self, input_data: Any) -> bool:
        return isinstance(input_data, dict) and "actor_a" in input_data and "actor_b" in input_data

    def extract(self, input_data: Dict[str, Any]) -> List[EvidenceUnit]:
        units = []
        actor_a = input_data.get("actor_a", "").strip()
        actor_b = input_data.get("actor_b", "").strip()
        raw_evidence = input_data.get("evidence", "")
        capture_id = input_data.get("capture_id", "cap_identity_init")
        captured_at = input_data.get("captured_at", datetime.now(timezone.utc).isoformat())
        source = input_data.get("source", "identity_graph")

        if not actor_a or not actor_b:
            return units

        # Standardize entity pair ordering
        left_entity = min(actor_a, actor_b)
        right_entity = max(actor_a, actor_b)
        linked_pair = [left_entity, right_entity]

        # 1. PGP Fingerprint Evidence
        if "PGP Fingerprint:" in raw_evidence:
            pgp_raw = raw_evidence.split("PGP Fingerprint:")[1].split(";")[0].strip()
            pgp_norm = self.normalize_pgp_fingerprint(pgp_raw)
            if pgp_norm:
                indep_group = f"indep_pgp_{hashlib.sha256(pgp_norm.encode()).hexdigest()[:16]}"
                is_signed = input_data.get("signature_verified", False)
                role = IndicatorRole.verified_signature.value if is_signed else IndicatorRole.key_published.value

                limitations = []
                if not is_signed:
                    limitations.append("Published key is not proof of key control. Verified signature required for high confidence.")

                units.append(EvidenceUnit(
                    evidence_id=f"ev_pgp_{hashlib.sha256(f'{left_entity}_{right_entity}_{pgp_norm}'.encode()).hexdigest()[:12]}",
                    schema_version="1.0.0",
                    capture_id=capture_id,
                    source=source,
                    source_version="1.0.0",
                    indicator_type=IndicatorType.pgp_fingerprint.value,
                    indicator_value=pgp_norm,
                    indicator_role=role,
                    linked_entities=linked_pair,
                    confidence_weight=0.95 if is_signed else 0.82,
                    source_reliability=1.0,
                    extraction_confidence=1.0,
                    source_claimed_time=input_data.get("source_claimed_time"),
                    observation_date=input_data.get("observation_date"),
                    captured_at=captured_at,
                    time_confidence=1.0,
                    source_url=input_data.get("source_url", f"identity://{left_entity}/{right_entity}"),
                    raw_evidence_hash=hashlib.sha256(raw_evidence.encode()).hexdigest(),
                    raw_evidence_reference=input_data.get("raw_reference", "fixtures/sample_data/personas.json"),
                    independence_group_id=indep_group,
                    collector_mode="fixture_replay",
                    processing_status=ProcessingStatus.valid.value,
                    explanation=f"Exact PGP fingerprint match between {left_entity} and {right_entity} ({pgp_norm}).",
                    limitations=limitations,
                    context_excerpt=f"Shared PGP Fingerprint: {pgp_norm}",
                    model_metadata={"normalizer": "pgp_uppercase_hex_v1"}
                ))

        # 2. Cryptocurrency Wallet Evidence
        if "Wallet Address:" in raw_evidence:
            wallet_raw = raw_evidence.split("Wallet Address:")[1].split(";")[0].strip()
            wallet_norm = self.normalize_wallet_address(wallet_raw)
            if wallet_norm:
                indep_group = f"indep_wallet_{hashlib.sha256(wallet_norm.encode()).hexdigest()[:16]}"
                is_mixer = "mixer" in wallet_norm.lower() or "shared" in wallet_norm.lower()
                role = IndicatorRole.mixer_suspected.value if is_mixer else IndicatorRole.wallet_unknown.value

                limitations = []
                confidence = 0.90
                if is_mixer:
                    confidence = 0.30
                    limitations.append("Shared escrow/mixer wallet address downweighted. Independent corroboration required.")

                units.append(EvidenceUnit(
                    evidence_id=f"ev_wallet_{hashlib.sha256(f'{left_entity}_{right_entity}_{wallet_norm}'.encode()).hexdigest()[:12]}",
                    schema_version="1.0.0",
                    capture_id=capture_id,
                    source=source,
                    source_version="1.0.0",
                    indicator_type=IndicatorType.wallet_address.value,
                    indicator_value=wallet_norm,
                    indicator_role=role,
                    linked_entities=linked_pair,
                    confidence_weight=confidence,
                    source_reliability=1.0,
                    extraction_confidence=1.0,
                    source_claimed_time=input_data.get("source_claimed_time"),
                    observation_date=input_data.get("observation_date"),
                    captured_at=captured_at,
                    time_confidence=1.0,
                    source_url=input_data.get("source_url", f"identity://{left_entity}/{right_entity}"),
                    raw_evidence_hash=hashlib.sha256(raw_evidence.encode()).hexdigest(),
                    raw_evidence_reference=input_data.get("raw_reference", "fixtures/sample_data/personas.json"),
                    independence_group_id=indep_group,
                    collector_mode="fixture_replay",
                    processing_status=ProcessingStatus.valid.value,
                    explanation=f"Cryptocurrency wallet address match between {left_entity} and {right_entity} ({wallet_norm}).",
                    limitations=limitations,
                    context_excerpt=f"Shared Wallet Address: {wallet_norm}",
                    model_metadata={"normalizer": "wallet_chain_v1"}
                ))

        return units

    @staticmethod
    def normalize_pgp_fingerprint(pgp_str: str) -> Optional[str]:
        cleaned = re.sub(r"[^A-Fa-f0-9]", "", pgp_str).upper()
        return cleaned if len(cleaned) == 40 else pgp_str.strip().upper()

    @staticmethod
    def normalize_wallet_address(wallet_str: str) -> Optional[str]:
        cleaned = wallet_str.strip()
        return cleaned if len(cleaned) >= 10 else None
