"""
Unit tests for CollectionNormalizer (Branch 2).
Tests MIME allowlist validation, 10MB size cap enforcement, script/style tag stripping,
binary sniffing, and quarantine path preservation per EC-03.
"""
import os
from collection.normalizer import CollectionNormalizer
from models.capture import Capture


def test_normalizer_safe_html():
    """Test safe HTML parsing removes active script/style elements without JS execution."""
    norm = CollectionNormalizer()
    raw = (
        b"<html><head><script>alert('malicious_js');</script>"
        b"<style>body { color: red; }</style></head>"
        b"<body><h1>GhostVendor Profile</h1>"
        b"<iframe src='http://evil.onion'></iframe>"
        b"<p>PGP: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678</p>"
        b"</body></html>"
    )
    safe_text, meta = norm.normalize(raw, "text/html")

    assert meta["status"] == "valid"
    assert "<script>" not in safe_text
    assert "alert" not in safe_text
    assert "<style>" not in safe_text
    assert "<iframe>" not in safe_text
    assert "GhostVendor Profile" in safe_text
    assert "1122 33AA BBCC" in safe_text


def test_normalizer_mime_validation():
    """Test MIME allowlist rejects and quarantines disallowed MIME types per EC-03."""
    norm = CollectionNormalizer()

    # Disallowed MIME types
    for bad_mime in ["application/x-executable", "image/png", "application/x-sh", "video/mp4"]:
        safe_text, meta = norm.normalize(b"binary_payload", content_type=bad_mime)
        assert meta["status"] == "quarantined"
        assert "not in allowlist" in meta["reason"]

    # Allowed MIME types
    for good_mime in ["text/html", "application/json", "text/plain"]:
        safe_text, meta = norm.normalize(b"valid content payload", content_type=good_mime)
        assert meta["status"] == "valid"


def test_normalizer_10mb_size_cap():
    """Test payloads exceeding 10MB are quarantined without parsing per EC-03."""
    norm = CollectionNormalizer()
    oversized_bytes = b"X" * (10 * 1024 * 1024 + 1024)  # 10MB + 1KB
    safe_text, meta = norm.normalize(oversized_bytes, "text/html")

    assert meta["status"] == "quarantined"
    assert "exceeds 10MB limit" in meta["reason"] or "exceeds limit" in meta["reason"]


def test_normalizer_oversized_fixture_file():
    """Test real oversized fixture file (fixtures/market-b/oversized.html >10MB) triggers quarantine."""
    norm = CollectionNormalizer()
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "fixtures",
        "market-b",
        "oversized.html",
    )
    assert os.path.exists(fixture_path), "oversized.html fixture must exist"

    with open(fixture_path, "rb") as f:
        content = f.read()

    assert len(content) > 10 * 1024 * 1024

    safe_text, meta = norm.normalize(content, "text/html")
    assert meta["status"] == "quarantined"
    assert "exceeds" in meta["reason"].lower()


def test_normalizer_binary_sniffing_quarantine():
    """Test binary/null-byte content in text payload triggers quarantine per EC-03."""
    norm = CollectionNormalizer()
    binary_content = b"<html><body>Normal start\x00\x00\x00\x01\x02\x03embedded binary</body></html>"
    safe_text, meta = norm.normalize(binary_content, "text/html")

    assert meta["status"] == "quarantined"
    assert "binary" in meta["reason"].lower() or "null" in meta["reason"].lower()


def test_normalizer_quarantine_path_preserves_metadata(temp_db):
    """Test quarantine path strictly preserves raw metadata without parsing per EC-03."""
    norm = CollectionNormalizer()
    cap = Capture(
        capture_id="cap_test_quarantine_01",
        source_id="fixture_market_b",
        url="fixture://market-b/oversized.html",
        mode="fixture_replay",
        authorization_status="approved",
        captured_at="2026-09-05T12:00:00Z",
        http_status=200,
        content_type="text/html",
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        raw_object_reference="fixtures/market-b/oversized.html",
        status="succeeded",
    )

    oversized_bytes = b"A" * (11 * 1024 * 1024)
    res = norm.normalize(cap, raw_content_bytes=oversized_bytes)

    # When called with Capture object, returns NormalizedPayload
    assert res.processing_status == "quarantined"
    assert "10MB" in res.quarantine_reason or "exceeds" in res.quarantine_reason.lower()
    assert res.raw_metadata["capture_id"] == "cap_test_quarantine_01"
    assert res.raw_metadata["url"] == "fixture://market-b/oversized.html"
    assert res.raw_metadata["sha256"] == cap.sha256
