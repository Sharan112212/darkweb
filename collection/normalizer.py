"""
CollectionNormalizer for SIH26151 Dark-Web Threat Actor Attribution Platform.
Validates MIME types against allowlist, enforces response size limits (<10MB),
extracts safe text/HTML metadata without JavaScript execution, and quarantines
malformed, oversized, or binary payloads while strictly preserving raw metadata (EC-03).
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Union
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import yaml

from models.capture import Capture
from models.enums import ProcessingStatus


class NormalizedPayload(BaseModel):
    """
    Standardized result of collection normalization.
    Preserves raw metadata alongside safe extracted text or quarantine state.
    """
    capture_id: str
    url: str
    processing_status: str  # valid | quarantined | parse_failed | redacted | superseded
    mime_type: str
    content_size_bytes: int
    extracted_text: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    links: List[Dict[str, str]] = Field(default_factory=list)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    quarantine_reason: Optional[str] = None


class CollectionNormalizer:
    """
    Normalizes captured content:
    - Validates MIME type against allowlist.
    - Validates response size (< 10MB).
    - Extracts safe text / HTML metadata without JS execution.
    - Quarantines malformed/oversized/binary content (preserving raw metadata — EC-03).
    """

    DEFAULT_MIME_ALLOWLIST = [
        "text/html",
        "application/json",
        "text/plain",
    ]

    DEFAULT_MAX_BYTES = 10485760  # 10 MB

    def __init__(
        self,
        mime_allowlist: Optional[List[str]] = None,
        max_response_bytes: Optional[int] = None,
        config_path: Optional[str] = None,
    ):
        self.mime_allowlist = mime_allowlist
        self.max_response_bytes = max_response_bytes

        if self.mime_allowlist is None or self.max_response_bytes is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cfg_file = config_path or os.path.join(project_root, "config", "source_policy.yaml")
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        policy = yaml.safe_load(f) or {}
                        if self.mime_allowlist is None:
                            self.mime_allowlist = policy.get("mime_allowlist", self.DEFAULT_MIME_ALLOWLIST)
                        if self.max_response_bytes is None:
                            self.max_response_bytes = policy.get("max_response_bytes", self.DEFAULT_MAX_BYTES)
                except Exception:
                    pass

        if self.mime_allowlist is None:
            self.mime_allowlist = list(self.DEFAULT_MIME_ALLOWLIST)
        if self.max_response_bytes is None:
            self.max_response_bytes = self.DEFAULT_MAX_BYTES

    @staticmethod
    def _parse_base_mime(content_type: Optional[str]) -> str:
        """Extracts the base MIME type without charset or attributes."""
        if not content_type:
            return "application/octet-stream"
        return content_type.split(";")[0].strip().lower()

    @staticmethod
    def _is_binary(content: bytes) -> bool:
        """
        Detects if byte buffer contains binary/executable content or null bytes.
        Checks initial 8192 bytes for null byte presence.
        """
        sample = content[:8192]
        return b"\x00" in sample

    def _build_raw_metadata(
        self,
        capture: Union[Capture, Dict[str, Any]],
        content_size: int,
    ) -> Dict[str, Any]:
        """Assembles raw metadata dictionary to preserve per EC-03."""
        if isinstance(capture, BaseModel):
            cap_dict = capture.model_dump()
        else:
            cap_dict = dict(capture)

        return {
            "capture_id": cap_dict.get("capture_id", ""),
            "source_id": cap_dict.get("source_id", ""),
            "url": cap_dict.get("url", ""),
            "mode": cap_dict.get("mode", ""),
            "authorization_status": cap_dict.get("authorization_status", ""),
            "captured_at": cap_dict.get("captured_at", ""),
            "http_status": cap_dict.get("http_status"),
            "content_type": cap_dict.get("content_type", ""),
            "sha256": cap_dict.get("sha256"),
            "raw_object_reference": cap_dict.get("raw_object_reference"),
            "status": cap_dict.get("status", ""),
            "not_collected_reason": cap_dict.get("not_collected_reason"),
            "size_bytes": content_size,
        }

    def normalize(
        self,
        capture: Union[Capture, Dict[str, Any], bytes],
        raw_content_bytes: Optional[Union[bytes, str]] = None,
    ) -> Union[NormalizedPayload, Tuple[str, Dict[str, Any]]]:
        """
        Normalizes a Capture payload or raw bytes.
        """
        if isinstance(capture, (bytes, bytearray)):
            content_bytes = bytes(capture)
            content_type = raw_content_bytes if isinstance(raw_content_bytes, str) else "text/html"
            base_mime = self._parse_base_mime(content_type)
            content_size = len(content_bytes)
            
            if base_mime not in self.mime_allowlist:
                return "", {"status": "quarantined", "reason": f"MIME type '{base_mime}' is not in allowlist per EC-03"}
            if content_size > self.max_response_bytes:
                return "", {"status": "quarantined", "reason": f"Content size {content_size} exceeds 10MB limit per EC-03"}
            if self._is_binary(content_bytes):
                return "", {"status": "quarantined", "reason": "Binary content or null bytes detected per EC-03"}

            try:
                safe_text = content_bytes.decode("utf-8", errors="replace")
                safe_text = re.sub(r"<script.*?>.*?</script>", "", safe_text, flags=re.DOTALL | re.IGNORECASE)
                safe_text = re.sub(r"<style.*?>.*?</style>", "", safe_text, flags=re.DOTALL | re.IGNORECASE)
            except Exception as e:
                return "", {"status": "quarantined", "reason": str(e)}

            return safe_text, {"status": "valid", "mime_type": base_mime, "size_bytes": content_size}

        if isinstance(capture, BaseModel):
            cap = capture
            cap_id = cap.capture_id
            url = cap.url
            content_type = cap.content_type or "text/html"
            ref_path = cap.raw_object_reference
        else:
            cap = capture
            cap_id = cap.get("capture_id", "")
            url = cap.get("url", "")
            content_type = cap.get("content_type", "text/html")
            ref_path = cap.get("raw_object_reference")

        # Resolve raw content bytes if not passed directly
        if raw_content_bytes is None:
            if ref_path and os.path.exists(ref_path):
                try:
                    with open(ref_path, "rb") as f:
                        raw_content_bytes = f.read()
                except Exception:
                    raw_content_bytes = None
            elif ref_path:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                alt_path = os.path.join(project_root, ref_path)
                if os.path.exists(alt_path):
                    try:
                        with open(alt_path, "rb") as f:
                            raw_content_bytes = f.read()
                    except Exception:
                        raw_content_bytes = None

        content_bytes = raw_content_bytes or b""
        content_size = len(content_bytes)
        base_mime = self._parse_base_mime(content_type)
        raw_metadata = self._build_raw_metadata(capture, content_size)

        # 1. Size Validation (< 10MB, EC-03)
        if content_size > self.max_response_bytes:
            return NormalizedPayload(
                capture_id=cap_id,
                url=url,
                processing_status=ProcessingStatus.quarantined.value,
                mime_type=base_mime,
                content_size_bytes=content_size,
                raw_metadata=raw_metadata,
                quarantine_reason=(
                    f"Payload size ({content_size} bytes) exceeds limit of "
                    f"{self.max_response_bytes} bytes per EC-03"
                ),
            )

        # 2. Empty payload check
        if content_size == 0:
            status = ProcessingStatus.parse_failed.value
            return NormalizedPayload(
                capture_id=cap_id,
                url=url,
                processing_status=status,
                mime_type=base_mime,
                content_size_bytes=0,
                raw_metadata=raw_metadata,
                quarantine_reason="Payload is empty (0 bytes)",
            )

        # 3. MIME Allowlist Validation (EC-03)
        if base_mime not in self.mime_allowlist:
            return NormalizedPayload(
                capture_id=cap_id,
                url=url,
                processing_status=ProcessingStatus.quarantined.value,
                mime_type=base_mime,
                content_size_bytes=content_size,
                raw_metadata=raw_metadata,
                quarantine_reason=f"MIME type '{base_mime}' is not in allowlist {self.mime_allowlist} per EC-03",
            )

        # 4. Binary Sniffing (EC-03)
        if self._is_binary(content_bytes):
            return NormalizedPayload(
                capture_id=cap_id,
                url=url,
                processing_status=ProcessingStatus.quarantined.value,
                mime_type=base_mime,
                content_size_bytes=content_size,
                raw_metadata=raw_metadata,
                quarantine_reason="Binary content or null bytes detected in text payload per EC-03",
            )

        # 5. Safe Decoding
        try:
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_content = content_bytes.decode("latin-1")
            except Exception as exc:
                return NormalizedPayload(
                    capture_id=cap_id,
                    url=url,
                    processing_status=ProcessingStatus.quarantined.value,
                    mime_type=base_mime,
                    content_size_bytes=content_size,
                    raw_metadata=raw_metadata,
                    quarantine_reason=f"Malformed content encoding: {str(exc)} per EC-03",
                )

        # 6. Safe Text / Metadata Extraction without JS Execution
        if base_mime == "text/html":
            return self._normalize_html(cap_id, url, text_content, content_size, base_mime, raw_metadata)
        elif base_mime == "application/json":
            return self._normalize_json(cap_id, url, text_content, content_size, base_mime, raw_metadata)
        else:
            # Plain text
            return NormalizedPayload(
                capture_id=cap_id,
                url=url,
                processing_status=ProcessingStatus.valid.value,
                mime_type=base_mime,
                content_size_bytes=content_size,
                extracted_text=text_content.strip(),
                raw_metadata=raw_metadata,
            )

    def _normalize_html(
        self,
        capture_id: str,
        url: str,
        html_str: str,
        content_size: int,
        mime_type: str,
        raw_metadata: Dict[str, Any],
    ) -> NormalizedPayload:
        """
        Parses HTML safely using html.parser (standard library, zero JS execution).
        Strips script, style, iframe tags and extracts clean text and metadata.
        """
        try:
            soup = BeautifulSoup(html_str, "html.parser")

            # Remove executable / active scripts and styling completely
            for element in soup(["script", "style", "iframe", "object", "embed", "noscript"]):
                element.decompose()

            # Extract Title
            title = soup.title.string.strip() if (soup.title and soup.title.string) else None

            # Extract Meta tags
            meta_dict: Dict[str, Any] = {}
            for tag in soup.find_all("meta"):
                name = tag.get("name") or tag.get("property")
                content = tag.get("content")
                if name and content:
                    meta_dict[str(name)] = str(content)

            # Extract Links safely
            links: List[Dict[str, str]] = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                link_text = a.get_text(strip=True)
                if href and not href.startswith("javascript:"):
                    links.append({"text": link_text, "href": href})

            # Extract plain text with normalized spacing
            text = soup.get_text(separator=" ", strip=True)
            normalized_text = re.sub(r"\s+", " ", text).strip()

            return NormalizedPayload(
                capture_id=capture_id,
                url=url,
                processing_status=ProcessingStatus.valid.value,
                mime_type=mime_type,
                content_size_bytes=content_size,
                extracted_text=normalized_text,
                title=title,
                metadata=meta_dict,
                links=links,
                raw_metadata=raw_metadata,
            )
        except Exception as exc:
            return NormalizedPayload(
                capture_id=capture_id,
                url=url,
                processing_status=ProcessingStatus.parse_failed.value,
                mime_type=mime_type,
                content_size_bytes=content_size,
                raw_metadata=raw_metadata,
                quarantine_reason=f"HTML parsing failed: {str(exc)}",
            )

    def _normalize_json(
        self,
        capture_id: str,
        url: str,
        json_str: str,
        content_size: int,
        mime_type: str,
        raw_metadata: Dict[str, Any],
    ) -> NormalizedPayload:
        """Parses and safely normalizes JSON content."""
        try:
            parsed = json.loads(json_str)
            text_repr = json.dumps(parsed, indent=2)
            meta = {}
            if isinstance(parsed, dict):
                meta = {k: v for k, v in parsed.items() if isinstance(v, (str, int, float, bool))}

            return NormalizedPayload(
                capture_id=capture_id,
                url=url,
                processing_status=ProcessingStatus.valid.value,
                mime_type=mime_type,
                content_size_bytes=content_size,
                extracted_text=text_repr,
                metadata=meta,
                raw_metadata=raw_metadata,
            )
        except json.JSONDecodeError as exc:
            return NormalizedPayload(
                capture_id=capture_id,
                url=url,
                processing_status=ProcessingStatus.parse_failed.value,
                mime_type=mime_type,
                content_size_bytes=content_size,
                raw_metadata=raw_metadata,
                quarantine_reason=f"Malformed JSON: {str(exc)} per EC-03",
            )
