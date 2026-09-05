"""
CaptureManager for SIH26151 Dark-Web Threat Actor Attribution Platform.
Manages raw artifact captures, SHA-256 hash generation, source policy checks,
MinIO/fixture archive storage, and Capture record persistence even on failures (EC-01).
"""

import fnmatch
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from db.repositories.capture_repo import CaptureRepository
from models.capture import Capture


class CaptureManager:
    """
    Orchestrates collection captures, policies, artifact hashing and storage,
    and database persistence via CaptureRepository.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config_dir: Optional[str] = None,
        archive_dir: Optional[str] = None,
    ):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_dir = config_dir or os.path.join(project_root, "config")
        self.archive_dir = archive_dir or os.path.join(project_root, "fixtures", "archive")
        os.makedirs(self.archive_dir, exist_ok=True)

        self.capture_repo = CaptureRepository(db_path)
        self.policy: Dict[str, Any] = self._load_policy()
        self.sources: List[Dict[str, Any]] = self._load_sources()

    def _load_policy(self) -> Dict[str, Any]:
        """Loads collection source policy from source_policy.yaml."""
        policy_path = os.path.join(self.config_dir, "source_policy.yaml")
        if os.path.exists(policy_path):
            try:
                with open(policy_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {
            "mode": "fixture_replay",
            "kill_switch": False,
            "default_timeout_seconds": 30,
            "max_response_bytes": 10485760,
            "max_retries": 2,
            "retry_backoff_seconds": 5,
            "request_delay_seconds": 2,
            "per_host_concurrency": 1,
            "mime_allowlist": ["text/html", "application/json", "text/plain"],
        }

    def _load_sources(self) -> List[Dict[str, Any]]:
        """Loads sources registry from sources.yaml."""
        sources_path = os.path.join(self.config_dir, "sources.yaml")
        if os.path.exists(sources_path):
            try:
                with open(sources_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("sources", [])
            except Exception:
                pass
        return []

    def reload_config(self) -> None:
        """Reloads policy and sources from disk."""
        self.policy = self._load_policy()
        self.sources = self._load_sources()

    def find_source(self, source_id: Optional[str] = None, url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Finds source definition by source_id or matching url_pattern."""
        if source_id:
            for s in self.sources:
                sid = s.get("id", "")
                if sid == source_id or sid == f"fixture_{source_id.replace('-', '_')}" or sid == f"{source_id}_source":
                    return s
        if url:
            for s in self.sources:
                pattern = s.get("url_pattern", "")
                if pattern and (fnmatch.fnmatch(url, pattern) or pattern.rstrip("*") in url):
                    return s
        return None

    def check_authorization(self, url: str, source_id: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Validates authorization for a given URL and source.
        Returns (authorization_status, failure_reason).
        EC-05: Source expiry and kill switch enforcement.
        """
        # Kill switch check
        if self.policy.get("kill_switch", False):
            return "blocked", "Collection kill switch is active"

        source = self.find_source(source_id=source_id, url=url)

        if source:
            if source.get("blocklisted", False):
                return "blocked", f"Source '{source.get('id')}' is blocklisted"

            # Check expiration date if set
            expires_at = source.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        return "expired", f"Source authorization expired at {expires_at} (EC-05)"
                except Exception:
                    pass

            status = source.get("authorization_status", "pending")
            if status != "approved":
                return status, f"Source authorization status is '{status}'"

            return "approved", None

        # If no explicit source entry, fixture URLs under fixture_replay mode are allowed by default
        if url.startswith("fixture://") and self.policy.get("mode") == "fixture_replay":
            return "approved", None

        return "pending", "No approved source authorization matches target URL"

    def is_source_allowlisted(self, url: str, source_id: Optional[str] = None) -> bool:
        """Check if source is authorized and allowed."""
        status, _ = self.check_authorization(url, source_id=source_id)
        return status == "approved"

    def store_raw_artifact(
        self,
        source_id: str,
        sha256_hash: str,
        raw_content_bytes: bytes,
        content_type: str = "text/html",
    ) -> str:
        """
        Stores raw artifact in MinIO or immutable local fixture archive.
        Returns raw object reference path.
        """
        ext = "json" if "json" in content_type else "html"

        # Check for MinIO environment credentials and client
        minio_endpoint = os.environ.get("MINIO_ENDPOINT")
        if minio_endpoint:
            try:
                from minio import Minio
                import io

                access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
                secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
                bucket_name = os.environ.get("MINIO_BUCKET", "raw-artifacts")
                client = Minio(
                    minio_endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=False,
                )
                if not client.bucket_exists(bucket_name):
                    client.make_bucket(bucket_name)

                object_name = f"{source_id}/{sha256_hash}.{ext}"
                client.put_object(
                    bucket_name,
                    object_name,
                    io.BytesIO(raw_content_bytes),
                    len(raw_content_bytes),
                    content_type=content_type,
                )
                return f"minio://{bucket_name}/{object_name}"
            except Exception:
                # Fall back to local fixture archive
                pass

        # Local fixture archive
        source_dir = os.path.join(self.archive_dir, source_id)
        os.makedirs(source_dir, exist_ok=True)
        file_name = f"{sha256_hash[:16]}.{ext}"
        full_path = os.path.join(source_dir, file_name)

        with open(full_path, "wb") as f:
            f.write(raw_content_bytes)

        # Return standardized relative reference path
        rel_path = f"fixtures/archive/{source_id}/{file_name}".replace("\\", "/")
        return rel_path

    def create_capture(
        self,
        source_id: str,
        url: str,
        raw_content_bytes: Optional[bytes] = None,
        status: str = "succeeded",
        http_status: Optional[int] = 200,
        not_collected_reason: Optional[str] = None,
        source_claimed_time: Optional[str] = None,
        content_type: Optional[str] = "text/html",
        captured_at: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Capture:
        """
        Creates a Capture record:
        - Checks authorization status.
        - Computes SHA-256 hash of raw_content_bytes.
        - Stores raw artifact in MinIO or fixture archive.
        - Saves Capture record to database (CaptureRepository).
        - Persists record even on failures (EC-01 status tracking).
        """
        captured_at = captured_at or datetime.now(timezone.utc).isoformat()
        collector_mode = mode or self.policy.get("mode", "fixture_replay")

        auth_status, auth_reason = self.check_authorization(url, source_id=source_id)
        if auth_status != "approved" and not not_collected_reason:
            not_collected_reason = auth_reason
            if status == "succeeded":
                status = "blocked"

        sha256_hash: Optional[str] = None
        raw_ref: Optional[str] = None

        if raw_content_bytes is not None:
            sha256_hash = hashlib.sha256(raw_content_bytes).hexdigest()
            raw_ref = self.store_raw_artifact(
                source_id=source_id,
                sha256_hash=sha256_hash,
                raw_content_bytes=raw_content_bytes,
                content_type=content_type or "text/html",
            )

        # Generate unique capture_id
        time_bucket = captured_at.replace(":", "").replace("-", "").replace(".", "")[:15]
        if sha256_hash:
            capture_id = f"cap_{source_id}_{sha256_hash[:8]}_{time_bucket}"
        else:
            short_id = uuid.uuid4().hex[:8]
            capture_id = f"cap_{source_id}_fail_{short_id}_{time_bucket}"

        capture_obj = Capture(
            capture_id=capture_id,
            source_id=source_id,
            url=url,
            mode=collector_mode,
            authorization_status=auth_status,
            captured_at=captured_at,
            source_claimed_time=source_claimed_time,
            http_status=http_status or 200,
            content_type=content_type or "text/html",
            sha256=sha256_hash or "0" * 64,
            raw_object_reference=raw_ref or "none",
            status=status,
            not_collected_reason=not_collected_reason,
        )

        saved = self.capture_repo.save(capture_obj.model_dump())
        return Capture(**saved) if isinstance(saved, dict) else saved

    # Alias for backwards compatibility
    def capture_content(
        self,
        source_id: str,
        url: str,
        content_bytes: bytes,
        status: str = "succeeded",
        http_status: int = 200,
        not_collected_reason: Optional[str] = None,
        source_claimed_time: Optional[str] = None,
        content_type: str = "text/html",
    ) -> Capture:
        """Alias for create_capture."""
        return self.create_capture(
            source_id=source_id,
            url=url,
            raw_content_bytes=content_bytes,
            status=status,
            http_status=http_status,
            not_collected_reason=not_collected_reason,
            source_claimed_time=source_claimed_time,
            content_type=content_type,
        )
