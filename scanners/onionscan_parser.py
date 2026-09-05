import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from models.evidence import EvidenceUnit
from models.enums import IndicatorType, ProcessingStatus

INDICATOR_WEIGHTS: Dict[str, float] = {
    IndicatorType.onionscan_analytics_id.value: 0.85,
    IndicatorType.onionscan_exif_leak.value: 0.75,
    IndicatorType.onionscan_server_status.value: 0.65,
    IndicatorType.onionscan_ssh_key.value: 0.60,
    IndicatorType.onionscan_certificate.value: 0.50,
    IndicatorType.onionscan_open_directory.value: 0.40,
}

class OnionScanParser:
    """
    Parses OnionScan JSON report structures into standardized Category I EvidenceUnit objects.
    Enforces exact weights from the Dev A Implementation Plan:
    - analytics_id = 0.85
    - exif_leak = 0.75
    - server_status = 0.65
    - ssh_key = 0.60
    - certificate = 0.50
    - open_directory = 0.40
    """

    def parse_report(
        self,
        report_data: Dict[str, Any],
        target_entity: str,
        capture_id: str = "cap_onionscan_init",
        captured_at: Optional[str] = None
    ) -> List[EvidenceUnit]:
        """
        Parses OnionScan report dict and produces EvidenceUnit records.
        """
        evidence_units: List[EvidenceUnit] = []
        if not report_data or not isinstance(report_data, dict):
            return evidence_units

        hidden_service = (
            report_data.get("hiddenService")
            or report_data.get("hidden_service")
            or report_data.get("target")
            or target_entity
        )
        hidden_service = str(hidden_service).strip().lower()

        if not captured_at:
            captured_at = report_data.get("date") or datetime.now(timezone.utc).isoformat()

        # 1. Analytics IDs (Weight: 0.85)
        analytics_ids = report_data.get("analyticsIDs") or report_data.get("analytics_ids") or report_data.get("analytics", [])
        if isinstance(analytics_ids, str):
            analytics_ids = [analytics_ids]
        for aid in analytics_ids:
            if not aid:
                continue
            val = str(aid).strip()
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_analytics_id.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan discovered Google Analytics / tracking ID '{val}' on {hidden_service}.",
                context_excerpt=f"Tracking ID: {val}"
            ))

        # 2. EXIF Leaks (Weight: 0.75)
        exif_leaks = report_data.get("exifLeaks") or report_data.get("exif_leaks") or report_data.get("exif", [])
        if isinstance(exif_leaks, (str, dict)):
            exif_leaks = [exif_leaks]
        for exif in exif_leaks:
            val = str(exif).strip()
            if not val:
                continue
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_exif_leak.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan detected EXIF metadata leak on {hidden_service}: {val[:80]}.",
                context_excerpt=f"EXIF Metadata: {val}"
            ))

        # 3. Server Status (Weight: 0.65)
        server_status = report_data.get("serverStatus") or report_data.get("server_status")
        if server_status:
            val = str(server_status).strip()
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_server_status.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan found exposed Apache/Nginx server status page on {hidden_service}.",
                context_excerpt=f"Server Status Info: {val}"
            ))

        # 4. SSH Keys (Weight: 0.60)
        ssh_keys = report_data.get("sshKeys") or report_data.get("ssh_keys") or report_data.get("ssh", [])
        if isinstance(ssh_keys, str):
            ssh_keys = [ssh_keys]
        for ssh in ssh_keys:
            val = str(ssh).strip()
            if not val:
                continue
            fingerprint = hashlib.sha256(val.encode()).hexdigest()[:16]
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_ssh_key.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan extracted SSH key fingerprint ({fingerprint}) from {hidden_service}.",
                context_excerpt=f"SSH Public Key: {val[:60]}..."
            ))

        # 5. TLS Certificates (Weight: 0.50)
        certs = report_data.get("certificates") or report_data.get("tls_certificates") or report_data.get("certs", [])
        if isinstance(certs, str):
            certs = [certs]
        for cert in certs:
            val = str(cert).replace(":", "").replace(" ", "").lower().strip()
            if not val:
                continue
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_certificate.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan discovered TLS Certificate fingerprint ({val[:16]}...) on {hidden_service}.",
                context_excerpt=f"Certificate Fingerprint: {val}"
            ))

        # 6. Open Directory (Weight: 0.40)
        open_dirs = report_data.get("openDirectories") or report_data.get("open_directories") or report_data.get("directories", [])
        if isinstance(open_dirs, str):
            open_dirs = [open_dirs]
        for odir in open_dirs:
            val = str(odir).strip()
            if not val:
                continue
            evidence_units.append(self._create_evidence(
                indicator_type=IndicatorType.onionscan_open_directory.value,
                indicator_value=val,
                target_entity=target_entity,
                hidden_service=hidden_service,
                capture_id=capture_id,
                captured_at=captured_at,
                explanation=f"OnionScan detected open directory listing at {val} on {hidden_service}.",
                context_excerpt=f"Open Directory: {val}"
            ))

        return evidence_units

    def _create_evidence(
        self,
        indicator_type: str,
        indicator_value: str,
        target_entity: str,
        hidden_service: str,
        capture_id: str,
        captured_at: str,
        explanation: str,
        context_excerpt: str
    ) -> EvidenceUnit:
        weight = INDICATOR_WEIGHTS.get(indicator_type, 0.50)
        val_hash = hashlib.sha256(indicator_value.encode()).hexdigest()[:16]
        indep_group = f"indep_onionscan_{indicator_type}_{val_hash}"

        left_entity = target_entity
        right_entity = f"infra_{hidden_service}"
        linked_pair = sorted([left_entity, right_entity])

        ev_id_hash = hashlib.sha256(f"{indicator_type}_{indicator_value}_{hidden_service}".encode()).hexdigest()[:12]

        return EvidenceUnit(
            evidence_id=f"ev_os_{ev_id_hash}",
            schema_version="1.0.0",
            category="I",
            capture_id=capture_id,
            source="onionscan",
            source_version="0.2.0",
            indicator_type=indicator_type,
            indicator_value=indicator_value,
            indicator_role=None,
            linked_entities=linked_pair,
            confidence_weight=weight,
            source_reliability=0.90,
            extraction_confidence=1.0,
            source_claimed_time=None,
            observation_date=None,
            captured_at=captured_at,
            time_confidence=1.0,
            source_url=f"http://{hidden_service}",
            raw_evidence_hash=hashlib.sha256(indicator_value.encode()).hexdigest(),
            raw_evidence_reference=f"fixtures/onionscan/{hidden_service}.json",
            independence_group_id=indep_group,
            collector_mode="fixture_replay",
            processing_status=ProcessingStatus.valid.value,
            explanation=explanation,
            limitations=[
                "Shared hosting or CDN infrastructure may cause false infrastructure correlation.",
                "Infrastructure evidence alone cannot exceed Possible Association tier."
            ],
            context_excerpt=context_excerpt,
            model_metadata={"indicator_weight": weight}
        )
