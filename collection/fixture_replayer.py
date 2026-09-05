import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from collection.capture_manager import CaptureManager
from models.capture import Capture


class FixtureReplayer:
    """
    Default collection engine that reads offline test fixtures and transitions,
    routing them through CaptureManager for standardized hashing, artifact storage,
    and database persistence.
    """

    def __init__(
        self,
        capture_manager: Optional[CaptureManager] = None,
        fixtures_dir: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fixtures_dir = fixtures_dir or os.path.join(project_root, "fixtures")
        if capture_manager:
            self.capture_manager = capture_manager
        elif db_path:
            self.capture_manager = CaptureManager(db_path=db_path)
        else:
            self.capture_manager = CaptureManager()
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Loads fixture manifest if available."""
        manifest_path = os.path.join(self.fixtures_dir, "manifests", "fixture_manifest.json")
        self.manifest: Dict[str, Any] = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    self.manifest = json.load(f)
            except Exception:
                pass

    def infer_source_id(self, url: str) -> str:
        """Infers registered source_id from fixture URL."""
        clean = url.replace("fixture://", "")
        parts = clean.split("/")
        market = parts[0] if parts else "market-a"
        if "market-a" in market:
            return "fixture_market_a"
        elif "market-b" in market:
            return "fixture_market_b"
        elif "blocked" in market:
            return "blocked_source"
        return f"fixture_{market.replace('-', '_')}"

    def resolve_fixture_file(
        self,
        url: str,
        stage: Optional[Union[str, int]] = None,
    ) -> Tuple[str, int, str, Optional[str]]:
        """
        Resolves fixture:// URL to file path and status.
        """
        clean = url.replace("fixture://", "")
        parts = clean.strip("/").split("/")
        market = parts[0]
        filename = parts[-1]

        if filename.endswith(".html"):
            base_name = filename[:-5]
        else:
            base_name = filename

        stage_str = str(stage).lower() if stage is not None else None
        if stage_str in ("1", "offline", "503"):
            target_name = f"{base_name.replace('_offline', '').replace('_changed', '')}_offline.html"
            http_status = 503
            status = "failed"
            reason = "Source offline: 503 Service Unavailable (EC-01)"
        elif stage_str in ("2", "changed", "updated"):
            target_name = f"{base_name.replace('_offline', '').replace('_changed', '')}_changed.html"
            http_status = 200
            status = "succeeded"
            reason = None
        elif stage_str in ("0", "online"):
            target_name = f"{base_name.replace('_offline', '').replace('_changed', '')}.html"
            http_status = 200
            status = "succeeded"
            reason = None
        else:
            if base_name.endswith("_offline"):
                target_name = f"{base_name}.html"
                http_status = 503
                status = "failed"
                reason = "Source offline: 503 Service Unavailable (EC-01)"
            elif base_name.endswith("_changed"):
                target_name = f"{base_name}.html"
                http_status = 200
                status = "succeeded"
                reason = None
            elif market == "blocked" or "captcha" in base_name:
                target_name = f"{base_name}.html"
                http_status = 403
                status = "blocked"
                reason = "CAPTCHA challenge detected; passive collection only per EC-04"
            else:
                target_name = f"{base_name}.html"
                http_status = 200
                status = "succeeded"
                reason = None

        candidate_path = os.path.join(self.fixtures_dir, market, target_name)
        if not os.path.exists(candidate_path):
            alt_path = os.path.join(self.fixtures_dir, f"{clean}.html")
            if os.path.exists(alt_path):
                candidate_path = alt_path
            else:
                raw_path = os.path.join(self.fixtures_dir, clean)
                if os.path.exists(raw_path):
                    candidate_path = raw_path

        return candidate_path, http_status, status, reason

    def get_fixture_bytes(
        self,
        url: str,
        stage: Optional[Union[str, int]] = None,
    ) -> bytes:
        """Reads raw bytes for a fixture URL."""
        file_path, _, _, _ = self.resolve_fixture_file(url, stage=stage)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fixture file not found: {file_path} for URL: {url}")
        with open(file_path, "rb") as f:
            return f.read()

    def fetch_fixture(
        self,
        url: str,
        source_id: Optional[str] = None,
        stage: Optional[Union[str, int]] = None,
    ) -> Tuple[Capture, bytes]:
        """
        Replays a fixture URL and returns tuple of (Capture, content_bytes).
        """
        capture = self.replay_url(url, source_id=source_id, stage=stage)
        try:
            content_bytes = self.get_fixture_bytes(url, stage=stage)
        except Exception:
            content_bytes = b""
        return capture, content_bytes

    def replay_url(
        self,
        url: str,
        source_id: Optional[str] = None,
        stage: Optional[Union[str, int]] = None,
        captured_at: Optional[str] = None,
        source_claimed_time: Optional[str] = None,
    ) -> Capture:
        """
        Replays a single fixture URL through CaptureManager.
        """
        src_id = source_id or self.infer_source_id(url)
        file_path, http_status, status, not_collected_reason = self.resolve_fixture_file(url, stage=stage)

        if not os.path.exists(file_path):
            return self.capture_manager.create_capture(
                source_id=src_id,
                url=url,
                raw_content_bytes=None,
                status="failed",
                http_status=404,
                not_collected_reason=f"Fixture not found at {file_path}",
                captured_at=captured_at,
                mode="fixture_replay",
            )

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        return self.capture_manager.create_capture(
            source_id=src_id,
            url=url,
            raw_content_bytes=raw_bytes,
            status=status,
            http_status=http_status,
            not_collected_reason=not_collected_reason,
            source_claimed_time=source_claimed_time,
            content_type="text/html",
            captured_at=captured_at,
            mode="fixture_replay",
        )

    def fetch_fixture(
        self,
        url: str,
        stage: Optional[Union[str, int]] = None,
    ) -> Tuple[Capture, bytes]:
        """
        Fetches and replays a fixture by URL, returning (Capture, content_bytes).
        """
        file_path, http_status, status, not_collected_reason = self.resolve_fixture_file(url, stage=stage)
        content_bytes = b""
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                content_bytes = f.read()
        capture = self.replay_url(url, stage=stage)
        if not content_bytes and capture.http_status == 503:
            content_bytes = b"503 Service Temporarily Unavailable"
        return capture, content_bytes

    def replay_transition(
        self,
        url: str,
        source_id: Optional[str] = None,
        base_time: Optional[datetime] = None,
    ) -> List[Capture]:
        """
        Replays a complete transition sequence for a target:
          1. Online profile (HTTP 200, status=succeeded)
          2. Offline outage (HTTP 503, status=failed, EC-01)
          3. Changed profile content after recovery (HTTP 200, status=succeeded)
        """
        src_id = source_id or self.infer_source_id(url)
        start = base_time or datetime.now(timezone.utc) - timedelta(hours=3)

        captures: List[Capture] = []
        t0 = start.isoformat()
        cap0 = self.replay_url(url, source_id=src_id, stage=0, captured_at=t0)
        captures.append(cap0)

        t1 = (start + timedelta(hours=1)).isoformat()
        cap1 = self.replay_url(url, source_id=src_id, stage=1, captured_at=t1)
        captures.append(cap1)

        t2 = (start + timedelta(hours=2)).isoformat()
        cap2 = self.replay_url(url, source_id=src_id, stage=2, captured_at=t2)
        captures.append(cap2)

        return captures

    def replay_all(self) -> List[Capture]:
        """
        Replays all standard fixtures registered in fixtures directory.
        """
        standard_urls = [
            "fixture://market-a/ghostvendor",
            "fixture://market-a/nightshade99",
            "fixture://market-b/mirror_ghostvendor",
            "fixture://market-b/mixer_pair_a",
            "fixture://market-b/mixer_pair_b",
            "fixture://market-b/oversized",
            "fixture://blocked/captcha_page",
        ]
        results: List[Capture] = []
        for u in standard_urls:
            results.append(self.replay_url(u))
        return results
