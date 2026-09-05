"""
Unit tests for FixtureReplayer (Branch 2).
Tests synthetic fixture loading, offline 503 simulation, missing fixture handling,
and canonical Capture output.
"""
from collection.fixture_replayer import FixtureReplayer
from models.capture import Capture


def test_fixture_replayer_success(temp_db):
    """Test loading valid fixture produces succeeded Capture output."""
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")

    assert isinstance(capture, Capture)
    assert capture.status == "succeeded"
    assert capture.http_status == 200
    assert b"GhostVendor" in content
    assert len(capture.sha256) == 64
    assert capture.authorization_status == "approved"
    assert capture.mode == "fixture_replay"


def test_fixture_replayer_offline_503(temp_db):
    """Test offline source fixture produces failed Capture with 503 status (EC-01)."""
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://market-a/ghostvendor_offline.html")

    assert isinstance(capture, Capture)
    assert capture.status == "failed"
    assert capture.http_status == 503
    assert b"503 Service Temporarily Unavailable" in content
    assert "503" in capture.not_collected_reason


def test_fixture_replayer_missing_fixture(temp_db):
    """Test non-existent fixture URL safely fails with durable status."""
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://market-a/does_not_exist_404.html")

    assert isinstance(capture, Capture)
    assert capture.status == "failed"
    assert capture.http_status == 503
    assert "missing" in capture.not_collected_reason.lower() or "offline" in capture.not_collected_reason.lower()


def test_fixture_replayer_blocked_source(temp_db):
    """Test blocked fixture path records blocked status and reason."""
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://blocked/captcha_page.html")

    assert isinstance(capture, Capture)
    assert capture.status == "blocked"
    assert capture.http_status == 403
    assert "blocked" in capture.not_collected_reason.lower()


def test_fixture_replayer_capture_schema_completeness(temp_db):
    """Verify all canonical Capture fields are populated per App Data Flow §4."""
    replayer = FixtureReplayer(db_path=temp_db)
    capture, _ = replayer.fetch_fixture("fixture://market-a/nightshade99.html")

    assert capture.capture_id is not None
    assert capture.source_id == "market-a"
    assert capture.url == "fixture://market-a/nightshade99.html"
    assert capture.mode == "fixture_replay"
    assert capture.authorization_status == "approved"
    assert capture.captured_at is not None
    assert capture.http_status == 200
    assert capture.content_type == "text/html"
    assert capture.sha256 is not None
    assert capture.raw_object_reference is not None
    assert capture.status == "succeeded"
