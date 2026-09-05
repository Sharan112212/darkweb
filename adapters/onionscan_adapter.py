"""
OnionScan Evidence Adapter (Branch 4).

Thin adapter at the canonical adapters/ path that wraps scanners.OnionScanParser
and applies Category-I post-processing required by the spec:

  - EC-08: rarity + freshness caveats and an infrastructure confidence cap so
    shared-hosting / CDN / stale-scan indicators cannot over-contribute.
  - Schema-version tracking for OnionScan output-format changes.

The heavy field-mapping lives in scanners/onionscan_parser.py; this adapter is
the stable seam other modules import.
"""
from typing import List, Dict, Any, Optional
from scanners.onionscan_parser import OnionScanParser
from models.evidence import EvidenceUnit

# Bump when OnionScan output mapping changes.
ONIONSCAN_ADAPTER_SCHEMA_VERSION = "1.0.0"

# Infrastructure evidence alone must not exceed the "possible association" band.
INFRA_CONFIDENCE_CAP = 0.65

# A scan older than this is treated as stale (EC-08).
STALE_SCAN_DAYS = 90


class OnionScanAdapter:
    """Maps OnionScan reports to capped, caveated Category-I EvidenceUnit records."""

    def __init__(self, parser: Optional[OnionScanParser] = None):
        self.parser = parser or OnionScanParser()
        self.schema_version = ONIONSCAN_ADAPTER_SCHEMA_VERSION

    def extract(
        self,
        report_data: Dict[str, Any],
        target_entity: str,
        capture_id: str = "cap_onionscan_init",
        rarity: Optional[float] = None,
        scan_age_days: Optional[int] = None,
        captured_at: Optional[str] = None,
    ) -> List[EvidenceUnit]:
        """
        Parse a report and apply EC-08 rarity/freshness caveats + the infra cap.

        Args:
            rarity: 0..1, higher = rarer = stronger. Values < 0.5 mark the
                indicator as common (shared hosting / CDN risk).
            scan_age_days: age of the scan; values > STALE_SCAN_DAYS mark it stale.
        """
        units = self.parser.parse_report(
            report_data=report_data,
            target_entity=target_entity,
            capture_id=capture_id,
            captured_at=captured_at,
        )
        return [self._apply_ec08(u, rarity, scan_age_days) for u in units]

    def _apply_ec08(
        self,
        unit: EvidenceUnit,
        rarity: Optional[float],
        scan_age_days: Optional[int],
    ) -> EvidenceUnit:
        # Rarity: down-weight and caveat common indicators.
        if rarity is not None:
            rarity = max(0.0, min(1.0, float(rarity)))
            unit.confidence_weight = round(unit.confidence_weight * rarity, 4)
            unit.model_metadata["rarity"] = rarity
            if rarity < 0.5:
                unit.limitations.append(
                    "Low-rarity indicator: observed across many hosts — likely shared "
                    "hosting / CDN rather than a unique operator link."
                )

        # Freshness: caveat + reduce time confidence for stale scans.
        if scan_age_days is not None:
            unit.model_metadata["scan_age_days"] = scan_age_days
            if scan_age_days > STALE_SCAN_DAYS:
                unit.limitations.append(
                    f"Stale scan: OnionScan data is {scan_age_days} days old; "
                    "infrastructure may have changed since collection."
                )
                unit.time_confidence = round(min(unit.time_confidence, 0.5), 4)

        # Hard infrastructure cap (EC-08): infra alone cannot exceed possible association.
        if unit.confidence_weight > INFRA_CONFIDENCE_CAP:
            unit.confidence_weight = INFRA_CONFIDENCE_CAP
            unit.model_metadata["infra_cap_applied"] = INFRA_CONFIDENCE_CAP

        unit.model_metadata["adapter_schema_version"] = self.schema_version
        return unit
