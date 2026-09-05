import os
import json
import logging
import shutil
import subprocess
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Iterable, Tuple
from scanners.base_scanner import BaseScanner
from scanners.onionscan_parser import OnionScanParser
from models.evidence import EvidenceUnit

logger = logging.getLogger(__name__)

# Hard defaults per Branch 4 spec.
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAX_OUTPUT_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_RAW_OUTPUT_DIR = "artifacts/onionscan"

# OnionScan output schema versions this adapter knows how to map. An unknown
# version marker is treated as a schema change (EC-07) rather than parsed blindly.
COMPATIBLE_SCHEMA_VERSIONS = {None, "", "0.2", "0.2.0", "0.3", "0.3.0", "1.0", "1.0.0"}


class ScanStatus:
    """Outcome of a single scan attempt (recorded in OnionScanRunner.last_result)."""
    SUCCESS = "success"
    EMPTY = "empty"
    BLOCKED = "blocked"          # target not on allowlist
    TIMEOUT = "timeout"          # scan timed out / partial
    ERROR = "error"             # scanner crash / missing binary / oversized
    SCHEMA_ERROR = "schema_error"  # unparseable or unknown output format (EC-07)


class OnionScanRunner(BaseScanner):
    """
    Executes or replays OnionScan infrastructure scans against target hidden services.

    Safety controls (Branch 4):
      - Target allowlist validation before any execution (audit event on block).
      - Hard timeout (default 120s) and output-size limit (default 5MB) on live runs.
      - Non-root execution guard for live runs (unless explicitly allowed).
      - Raw output + SHA-256 hash preserved for EVERY attempt, regardless of
        parse success (EC-07).
      - Structured status detection for timeout / error / schema-change fixtures.
      - Graceful fallback to synthetic fixture replay; never raises into the
        pipeline (emits 0 evidence units on any failure).
    """

    def __init__(
        self,
        onionscan_binary: str = "onionscan",
        mode: str = "fixture_replay",
        fixtures_dir: str = "fixtures/onionscan",
        allowlist: Optional[Iterable[str]] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        allow_root: bool = False,
        raw_output_dir: str = DEFAULT_RAW_OUTPUT_DIR,
        audit_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.onionscan_binary = onionscan_binary
        self.mode = mode
        self.fixtures_dir = fixtures_dir
        # allowlist=None => allow all (opt-in enforcement); a set => enforce membership.
        self.allowlist = None if allowlist is None else {self._normalize(t) for t in allowlist}
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.allow_root = allow_root
        self.raw_output_dir = raw_output_dir
        self.audit_sink = audit_sink
        self.parser = OnionScanParser()
        # Metadata of the most recent scan attempt.
        self.last_result: Dict[str, Any] = {}

    # ------------------------------------------------------------------ public

    def scan(
        self,
        target: str,
        capture_id: str = "cap_onionscan_init",
        fixture_path: Optional[str] = None,
        target_entity: str = "actor_unknown",
        **kwargs: Any,
    ) -> List[EvidenceUnit]:
        """
        Runs OnionScan or replays a fixture for target. Always returns a list of
        EvidenceUnit (empty on any failure). Detailed outcome is in self.last_result.
        """
        hidden_service = self._normalize(target)

        # 1. Allowlist validation (EC before any execution) -----------------
        if not self._is_allowed(hidden_service):
            self._record(hidden_service, ScanStatus.BLOCKED, capture_id,
                         error="target not on allowlist")
            self._emit_audit("onionscan_scan_blocked", hidden_service,
                             "Target not on allowlist; scan refused.")
            logger.warning(f"OnionScan target '{hidden_service}' not on allowlist — scan blocked.")
            return []

        # 2. Obtain raw output text ----------------------------------------
        if self.mode == "fixture_replay" or fixture_path:
            raw_text = self._load_fixture_raw(hidden_service, fixture_path)
        else:
            raw_text = self._execute_onionscan_raw(hidden_service, capture_id)

        if raw_text is None:
            # _execute_onionscan_raw already recorded a precise status; only record
            # EMPTY here if nothing has been recorded for this attempt yet.
            if self.last_result.get("target") != hidden_service:
                self._record(hidden_service, ScanStatus.EMPTY, capture_id,
                             error="no report produced")
            return []

        # 3. Persist raw output + hash for EVERY attempt (EC-07) -----------
        raw_hash, raw_path = self._persist_raw(hidden_service, raw_text, capture_id)

        # 4. Parse + classify outcome --------------------------------------
        return self._process_report(
            raw_text=raw_text,
            raw_hash=raw_hash,
            raw_path=raw_path,
            hidden_service=hidden_service,
            target_entity=target_entity,
            capture_id=capture_id,
        )

    # -------------------------------------------------------------- internals

    @staticmethod
    def _normalize(target: str) -> str:
        return (
            str(target)
            .replace("http://", "")
            .replace("https://", "")
            .strip()
            .strip("/")
            .lower()
        )

    def _is_allowed(self, hidden_service: str) -> bool:
        if self.allowlist is None:
            return True
        base = hidden_service.replace(".onion", "")
        return hidden_service in self.allowlist or base in self.allowlist

    def _process_report(
        self,
        raw_text: str,
        raw_hash: str,
        raw_path: Optional[str],
        hidden_service: str,
        target_entity: str,
        capture_id: str,
    ) -> List[EvidenceUnit]:
        # 4a. JSON decode ---------------------------------------------------
        try:
            report_data = json.loads(raw_text)
        except Exception as e:  # noqa: BLE001 - unparseable output is a schema change
            self._record(hidden_service, ScanStatus.SCHEMA_ERROR, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path, error=f"invalid JSON: {e}")
            logger.warning(f"OnionScan output for {hidden_service} is not valid JSON (EC-07 schema error).")
            return []

        if not isinstance(report_data, dict):
            self._record(hidden_service, ScanStatus.SCHEMA_ERROR, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path,
                         error="top-level report is not an object")
            return []

        # 4b. Explicit scanner error output --------------------------------
        if report_data.get("error"):
            self._record(hidden_service, ScanStatus.ERROR, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path,
                         error=str(report_data.get("error")))
            logger.warning(f"OnionScan reported an error for {hidden_service}: {report_data.get('error')}")
            return []

        # 4c. Timeout / partial output -------------------------------------
        status_field = str(report_data.get("status", "")).lower()
        if status_field in ("timeout", "timed_out") or report_data.get("timeout") is True or report_data.get("partial") is True:
            self._record(hidden_service, ScanStatus.TIMEOUT, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path,
                         error="scan timed out / partial result")
            logger.warning(f"OnionScan timed out / returned partial result for {hidden_service} (EC-07).")
            return []

        # 4d. Unknown output schema version --------------------------------
        version = report_data.get("onionScanVersion") or report_data.get("onionscan_version") or report_data.get("schema_version")
        if version not in COMPATIBLE_SCHEMA_VERSIONS:
            self._record(hidden_service, ScanStatus.SCHEMA_ERROR, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path,
                         error=f"unsupported OnionScan schema version: {version}")
            logger.warning(f"OnionScan output for {hidden_service} uses unsupported schema '{version}' (EC-07).")
            return []

        # 4e. Map to EvidenceUnit ------------------------------------------
        try:
            units = self.parser.parse_report(
                report_data=report_data,
                target_entity=target_entity,
                capture_id=capture_id,
            )
        except Exception as e:  # noqa: BLE001 - defensive: any mapping error is a schema change
            self._record(hidden_service, ScanStatus.SCHEMA_ERROR, capture_id,
                         raw_hash=raw_hash, raw_path=raw_path,
                         error=f"parser failure: {e}")
            logger.warning(f"OnionScan parser failed for {hidden_service} (EC-07 schema error): {e}")
            return []

        status = ScanStatus.SUCCESS if units else ScanStatus.EMPTY
        self._record(hidden_service, status, capture_id, raw_hash=raw_hash,
                     raw_path=raw_path, unit_count=len(units))
        return units

    def _load_fixture_raw(self, hidden_service: str, explicit_path: Optional[str] = None) -> Optional[str]:
        """Loads the raw text of a JSON fixture (so the exact bytes can be hashed)."""
        candidates = []
        if explicit_path:
            candidates.append(explicit_path)

        base_name = hidden_service.replace(".onion", "")
        candidates.extend([
            os.path.join(self.fixtures_dir, f"{hidden_service}.json"),
            os.path.join(self.fixtures_dir, f"{base_name}.json"),
            os.path.join(self.fixtures_dir, f"{hidden_service}_onionscan.json"),
            os.path.join(self.fixtures_dir, f"{base_name}_onionscan.json"),
            os.path.join(self.fixtures_dir, "default_onionscan.json"),
        ])

        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Failed to read OnionScan fixture at {path}: {e}")

        logger.warning(f"No valid OnionScan fixture found for {hidden_service} in {candidates}")
        return None

    def _execute_onionscan_raw(self, hidden_service: str, capture_id: str) -> Optional[str]:
        """
        Executes the live OnionScan binary as a restricted subprocess and returns
        its raw stdout text. Enforces non-root, timeout, and output-size limits.
        Records a precise failure status; never raises.
        """
        # Non-root guard (POSIX only; Windows has no geteuid).
        geteuid = getattr(os, "geteuid", None)
        if not self.allow_root and geteuid is not None and geteuid() == 0:
            self._record(hidden_service, ScanStatus.ERROR, capture_id,
                         error="refusing to run OnionScan as root (set allow_root=True to override)")
            logger.error("Refusing to run OnionScan as root. Run as a non-root user or via the isolated container.")
            return None

        if not shutil.which(self.onionscan_binary):
            self._record(hidden_service, ScanStatus.ERROR, capture_id,
                         error=f"binary '{self.onionscan_binary}' not found on PATH")
            logger.warning(f"OnionScan binary '{self.onionscan_binary}' not found on PATH (EC-07 fallback).")
            return None

        try:
            cmd = [self.onionscan_binary, "--json", hidden_service]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if result.returncode != 0:
                self._record(hidden_service, ScanStatus.ERROR, capture_id,
                             error=f"exit code {result.returncode}: {result.stderr[:500]}")
                logger.warning(f"OnionScan exited {result.returncode} for {hidden_service}: {result.stderr[:200]}")
                return None

            output = result.stdout or ""
            if len(output.encode("utf-8", errors="ignore")) > self.max_output_bytes:
                self._record(hidden_service, ScanStatus.ERROR, capture_id,
                             error=f"output exceeded {self.max_output_bytes} bytes")
                logger.warning(f"OnionScan output for {hidden_service} exceeded {self.max_output_bytes} bytes — discarded.")
                return None

            return output
        except subprocess.TimeoutExpired:
            self._record(hidden_service, ScanStatus.TIMEOUT, capture_id,
                         error=f"timed out after {self.timeout_seconds}s")
            logger.warning(f"OnionScan timed out after {self.timeout_seconds}s scanning {hidden_service} (EC-07).")
            return None
        except Exception as e:  # noqa: BLE001
            self._record(hidden_service, ScanStatus.ERROR, capture_id, error=str(e))
            logger.warning(f"OnionScan execution failed for {hidden_service}: {e}")
            return None

    def _persist_raw(self, hidden_service: str, raw_text: str, capture_id: str) -> Tuple[str, Optional[str]]:
        """
        Computes the SHA-256 of the raw output and writes it to raw_output_dir.
        The hash is always returned; a write failure never aborts the scan.
        """
        raw_bytes = raw_text.encode("utf-8", errors="ignore")
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        raw_path: Optional[str] = None
        try:
            os.makedirs(self.raw_output_dir, exist_ok=True)
            safe = hidden_service.replace("/", "_").replace(".onion", "")
            raw_path = os.path.join(self.raw_output_dir, f"{safe}_{raw_hash[:12]}.json")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
        except Exception as e:  # noqa: BLE001 - persistence is best-effort
            logger.warning(f"Could not persist raw OnionScan output for {hidden_service}: {e}")
            raw_path = None
        return raw_hash, raw_path

    def _record(
        self,
        hidden_service: str,
        status: str,
        capture_id: str,
        raw_hash: Optional[str] = None,
        raw_path: Optional[str] = None,
        error: Optional[str] = None,
        unit_count: int = 0,
    ) -> None:
        self.last_result = {
            "target": hidden_service,
            "capture_id": capture_id,
            "status": status,
            "raw_output_sha256": raw_hash,
            "raw_output_path": raw_path,
            "error": error,
            "unit_count": unit_count,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def _emit_audit(self, event_type: str, target: str, message: str) -> None:
        event = {
            "event_type": event_type,
            "target": target,
            "message": message,
            "source": "onionscan_runner",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.audit_sink is not None:
            try:
                self.audit_sink(event)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Audit sink failed for event {event_type}: {e}")
        else:
            logger.info(f"AUDIT {event_type}: {message} (target={target})")
