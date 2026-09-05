from collection.capture_manager import CaptureManager

def test_capture_manager_creation(temp_db):
    cm = CaptureManager(temp_db)
    content = b"<html><body>GhostVendor profile test</body></html>"
    capture = cm.capture_content(
        source_id="fixture_market_a",
        url="fixture://market-a/ghostvendor.html",
        content_bytes=content,
        status="succeeded"
    )

    assert capture.capture_id.startswith("cap_fixture_market_a")
    assert capture.status == "succeeded"
    assert len(capture.sha256) == 64

def test_capture_manager_failure_record(temp_db):
    cm = CaptureManager(temp_db)
    error_bytes = b"503 Service Temporarily Unavailable"
    capture = cm.capture_content(
        source_id="fixture_market_a",
        url="fixture://market-a/ghostvendor_offline.html",
        content_bytes=error_bytes,
        status="failed",
        http_status=503,
        not_collected_reason="Source offline"
    )

    assert capture.status == "failed"
    assert capture.http_status == 503
    assert capture.not_collected_reason == "Source offline"
