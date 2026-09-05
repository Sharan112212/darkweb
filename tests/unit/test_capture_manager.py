"""
Unit tests for CaptureManager (Branch 2).
Tests Capture record creation, SHA-256 computation, failure status recording (EC-01),
and idempotency persistence.
"""
import hashlib
from collection.capture_manager import CaptureManager
from models.capture import Capture


def test_capture_manager_creation(temp_db):
    """Test standard successful Capture record creation."""
    cm = CaptureManager(temp_db)
    content = b"<html><body>GhostVendor profile test</body></html>"
    capture = cm.capture_content(
        source_id="fixture_market_a",
        url="fixture://market-a/ghostvendor.html",
        content_bytes=content,
        status="succeeded",
        http_status=200,
        content_type="text/html",
    )

    assert isinstance(capture, Capture)
    assert capture.capture_id.startswith("cap_fixture_market_a")
    assert capture.status == "succeeded"
    assert capture.http_status == 200
    assert capture.content_type == "text/html"
    assert capture.authorization_status == "approved"
    assert capture.raw_object_reference is not None


def test_capture_manager_sha256_computation(temp_db):
    """Test cryptographic SHA-256 computation on raw artifacts."""
    cm = CaptureManager(temp_db)
    content = b"Cryptographic content checksum verification payload"
    expected_hash = hashlib.sha256(content).hexdigest()

    capture = cm.capture_content(
        source_id="fixture_market_a",
        url="fixture://market-a/checksum.html",
        content_bytes=content,
        status="succeeded",
    )

    assert len(capture.sha256) == 64
    assert capture.sha256 == expected_hash


def test_capture_manager_failure_status_recording(temp_db):
    """
    Test failure status recording (EC-01).
    Ensures a failed source produces a durable status record, not deleted evidence.
    """
    cm = CaptureManager(temp_db)
    error_bytes = b"503 Service Temporarily Unavailable"
    capture = cm.capture_content(
        source_id="fixture_market_a",
        url="fixture://market-a/ghostvendor_offline.html",
        content_bytes=error_bytes,
        status="failed",
        http_status=503,
        not_collected_reason="Source offline (503 Service Temporarily Unavailable)",
    )

    assert capture.status == "failed"
    assert capture.http_status == 503
    assert capture.not_collected_reason == "Source offline (503 Service Temporarily Unavailable)"

    # Verify durability in database
    fetched = cm.capture_repo.get_by_id(capture.capture_id)
    assert fetched is not None
    assert fetched["status"] == "failed"
    assert fetched["http_status"] == 503
    assert fetched["not_collected_reason"] == "Source offline (503 Service Temporarily Unavailable)"


def test_capture_manager_idempotency(temp_db):
    """Test idempotency constraints on Capture saving."""
    cm = CaptureManager(temp_db)
    content = b"Idempotent raw capture test payload"
    captured_at = "2026-09-05T12:00:00Z"

    cap1 = cm.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/idempotent.html",
        raw_content_bytes=content,
        status="succeeded",
        captured_at=captured_at,
    )

    cap2 = cm.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/idempotent.html",
        raw_content_bytes=content,
        status="succeeded",
        captured_at=captured_at,
    )

    assert cap1.capture_id == cap2.capture_id
    assert cap1.sha256 == cap2.sha256
