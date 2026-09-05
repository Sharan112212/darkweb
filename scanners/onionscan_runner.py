import os
import json
import logging
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from scanners.base_scanner import BaseScanner
from scanners.onionscan_parser import OnionScanParser
from models.evidence import EvidenceUnit

logger = logging.getLogger(__name__)

class OnionScanRunner(BaseScanner):
    """
    Executes or replays OnionScan infrastructure scans against target hidden services.
    Provides graceful fallback to synthetic fixture replay and handles offline/missing binary errors (EC-07).
    """

    def __init__(
        self,
        onionscan_binary: str = "onionscan",
        mode: str = "fixture_replay",
        fixtures_dir: str = "fixtures/onionscan"
    ):
        self.onionscan_binary = onionscan_binary
        self.mode = mode
        self.fixtures_dir = fixtures_dir
        self.parser = OnionScanParser()

    def scan(
        self,
        target: str,
        capture_id: str = "cap_onionscan_init",
        fixture_path: Optional[str] = None,
        target_entity: str = "actor_unknown",
        **kwargs: Any
    ) -> List[EvidenceUnit]:
        """
        Runs OnionScan or replays fixture for target.
        Emits zero evidence units on failure (EC-07).
        """
        hidden_service = target.replace("http://", "").replace("https://", "").strip("/")

        report_data = None

        if self.mode == "fixture_replay" or fixture_path:
            report_data = self._load_fixture(hidden_service, fixture_path)
        else:
            report_data = self._execute_onionscan(hidden_service)

        if not report_data:
            logger.warning(f"OnionScan scan for {hidden_service} returned no report (EC-07 graceful failure). Emitting 0 evidence units.")
            return []

        return self.parser.parse_report(
            report_data=report_data,
            target_entity=target_entity,
            capture_id=capture_id
        )

    def _load_fixture(self, hidden_service: str, explicit_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Loads JSON fixture from file path."""
        candidates = []
        if explicit_path:
            candidates.append(explicit_path)
        
        base_name = hidden_service.replace(".onion", "")

        candidates.extend([
            os.path.join(self.fixtures_dir, f"{hidden_service}.json"),
            os.path.join(self.fixtures_dir, f"{base_name}.json"),
            os.path.join(self.fixtures_dir, f"{hidden_service}_onionscan.json"),
            os.path.join(self.fixtures_dir, f"{base_name}_onionscan.json"),
            os.path.join(self.fixtures_dir, "default_onionscan.json")
        ])

        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read OnionScan fixture at {path}: {e}")
        
        logger.warning(f"No valid OnionScan fixture found for {hidden_service} in {candidates}")
        return None

    def _execute_onionscan(self, hidden_service: str) -> Optional[Dict[str, Any]]:
        """
        Executes live OnionScan binary via subprocess.
        Handles missing binary, timeout, and execution failures safely (EC-07).
        """
        if not shutil.which(self.onionscan_binary):
            logger.warning(f"OnionScan binary '{self.onionscan_binary}' not found on PATH. Falling back to 0 evidence units (EC-07).")
            return None

        try:
            cmd = [self.onionscan_binary, "--json", hidden_service]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"OnionScan process exited with code {result.returncode}: {result.stderr}")
                return None

            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            logger.warning(f"OnionScan timed out scanning target {hidden_service}")
            return None
        except Exception as e:
            logger.warning(f"OnionScan execution failed for {hidden_service}: {e}")
            return None
