"""
Comprehensive unit tests for collection framework modules:
- CaptureManager (policy, hashing, persistence, EC-01)
- FixtureReplayer (fixture:// replaying, transition fixtures)
- TorCollector (SOCKS5h enforcement, pacing, passive EC-04)
- CollectionNormalizer (MIME allowlist, size limits, JS stripping, EC-03)
"""

import os
import tempfile
import pytest
import yaml

from collection import (
    CaptureManager,
    FixtureReplayer,
    TorCollector,
    CollectionNormalizer,
    NormalizedPayload,
)
from models.capture import Capture
from models.enums import ProcessingStatus


@pytest.fixture
def temp_capture_mgr(temp_db):
    """Initializes a CaptureManager with temporary DB and archive folder."""
    with tempfile.TemporaryDirectory() as temp_archive:
        mgr = CaptureManager(db_path=temp_db, archive_dir=temp_archive)
        yield mgr


# ---------------------------------------------------------------------------
# 1. Config Loading & Sources Tests
# ---------------------------------------------------------------------------

def test_source_policy_file_exists():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    policy_path = os.path.join(project_root, "config", "source_policy.yaml")
    assert os.path.exists(policy_path), "source_policy.yaml must exist"

    with open(policy_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["mode"] == "fixture_replay"
    assert data["kill_switch"] is False
    assert data["default_timeout_seconds"] == 30
    assert data["max_response_bytes"] == 10485760
    assert "text/html" in data["mime_allowlist"]


def test_sources_registry_file_exists():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sources_path = os.path.join(project_root, "config", "sources.yaml")
    assert os.path.exists(sources_path), "sources.yaml must exist"

    with open(sources_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    assert len(sources) >= 3
    source_ids = [s["id"] for s in sources]
    assert "fixture_market_a" in source_ids
    assert "fixture_market_b" in source_ids
    assert "blocked_source" in source_ids

    blocked = next(s for s in sources if s["id"] == "blocked_source")
    assert blocked["blocklisted"] is True


# ---------------------------------------------------------------------------
# 2. CaptureManager Tests
# ---------------------------------------------------------------------------

def test_capture_manager_create_capture_success(temp_capture_mgr):
    mgr = temp_capture_mgr
    raw_html = b"<html><body><h1>Test Vendor</h1></body></html>"
    url = "fixture://market-a/test"

    cap = mgr.create_capture(
        source_id="fixture_market_a",
        url=url,
        raw_content_bytes=raw_html,
        status="succeeded",
        http_status=200,
    )

    assert isinstance(cap, Capture)
    assert cap.source_id == "fixture_market_a"
    assert cap.url == url
    assert cap.status == "succeeded"
    assert cap.http_status == 200
    assert len(cap.sha256) == 64
    assert cap.raw_object_reference is not None
    assert "fixtures/archive" in cap.raw_object_reference

    # Verify retrieved from DB
    persisted = mgr.capture_repo.get_by_id(cap.capture_id)
    assert persisted is not None
    assert persisted["sha256"] == cap.sha256


def test_capture_manager_records_failure_ec01(temp_capture_mgr):
    """EC-01: Status tracking must persist records even when collection fails."""
    mgr = temp_capture_mgr
    cap = mgr.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/offline-page",
        raw_content_bytes=None,
        status="failed",
        http_status=503,
        not_collected_reason="Source offline: 503 Service Unavailable (EC-01)",
    )

    assert isinstance(cap, Capture)
    assert cap.status == "failed"
    assert cap.http_status == 503
    assert "EC-01" in cap.not_collected_reason

    # Verify DB persistence of failed capture
    persisted = mgr.capture_repo.get_by_id(cap.capture_id)
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert persisted["http_status"] == 503


def test_capture_manager_blocklist_and_kill_switch(temp_capture_mgr):
    mgr = temp_capture_mgr

    # 1. Blocklisted source check
    status, reason = mgr.check_authorization("fixture://blocked/something", source_id="blocked_source")
    assert status == "blocked"

    # 2. Kill switch check
    mgr.policy["kill_switch"] = True
    status, reason = mgr.check_authorization("fixture://market-a/ghostvendor")
    assert status == "blocked"
    assert "kill switch" in reason.lower()


# ---------------------------------------------------------------------------
# 3. FixtureReplayer Tests
# ---------------------------------------------------------------------------

def test_fixture_replayer_single_url(temp_capture_mgr):
    replayer = FixtureReplayer(capture_manager=temp_capture_mgr)
    cap = replayer.replay_url("fixture://market-a/ghostvendor")

    assert isinstance(cap, Capture)
    assert cap.source_id == "fixture_market_a"
    assert cap.status == "succeeded"
    assert cap.http_status == 200
    assert cap.sha256 == "023e04327231c77324cd208392f7dc22a823a4f031c64bb6dc658c36df9710a8"


def test_fixture_replayer_transitions_ec01(temp_capture_mgr):
    """Tests full transition replay: online -> offline 503 -> changed content."""
    replayer = FixtureReplayer(capture_manager=temp_capture_mgr)
    caps = replayer.replay_transition("fixture://market-a/ghostvendor")

    assert len(caps) == 3

    # Stage 0: Online
    assert caps[0].status == "succeeded"
    assert caps[0].http_status == 200
    assert caps[0].sha256 == "023e04327231c77324cd208392f7dc22a823a4f031c64bb6dc658c36df9710a8"

    # Stage 1: Offline 503 (EC-01)
    assert caps[1].status == "failed"
    assert caps[1].http_status == 503
    assert "503 Service Unavailable" in (caps[1].not_collected_reason or "")

    # Stage 2: Changed
    assert caps[2].status == "succeeded"
    assert caps[2].http_status == 200
    assert caps[2].sha256 == "f7024cc617159938b614593798328e145a9d2006096a8990d3809de5f7f0278f"
    assert caps[2].sha256 != caps[0].sha256


def test_fixture_replayer_blocked_captcha(temp_capture_mgr):
    """EC-04: Passive collection records reason on CAPTCHA fixture."""
    replayer = FixtureReplayer(capture_manager=temp_capture_mgr)
    cap = replayer.replay_url("fixture://blocked/captcha_page")

    assert cap.status == "blocked"
    assert "EC-04" in (cap.not_collected_reason or "")


# ---------------------------------------------------------------------------
# 4. TorCollector Tests
# ---------------------------------------------------------------------------

def test_tor_collector_proxy_hardening_ec06(temp_capture_mgr):
    """EC-06: TorCollector must reject any scheme other than socks5h://."""
    # socks5h is accepted
    collector = TorCollector(proxy_url="socks5h://127.0.0.1:9050", capture_manager=temp_capture_mgr)
    assert collector.proxy_url == "socks5h://127.0.0.1:9050"

    # Insecure schemes must be rejected
    with pytest.raises(ValueError, match="socks5h://"):
        TorCollector(proxy_url="socks5://127.0.0.1:9050", capture_manager=temp_capture_mgr)

    with pytest.raises(ValueError, match="socks5h://"):
        TorCollector(proxy_url="http://127.0.0.1:8080", capture_manager=temp_capture_mgr)


def test_tor_collector_detects_captcha_ec04(temp_capture_mgr):
    """EC-04: Passive collection detects CAPTCHA patterns without submitting."""
    collector = TorCollector(capture_manager=temp_capture_mgr)

    html_captcha = """
    <html><body>
    <form action="/verify" method="POST">
        <div class="g-recaptcha" data-sitekey="xyz"></div>
        <button type="submit">Submit</button>
    </form>
    </body></html>
    """
    is_blocked, reason = collector.detect_passive_blocking(html_captcha)
    assert is_blocked is True
    assert "EC-04" in reason

    login_html = "<html><body><input type='password' name='pass'>Please login to continue</body></html>"
    is_blocked_login, login_reason = collector.detect_passive_blocking(login_html)
    assert is_blocked_login is True
    assert "EC-04" in login_reason


# ---------------------------------------------------------------------------
# 5. CollectionNormalizer Tests
# ---------------------------------------------------------------------------

def test_normalizer_valid_html(temp_capture_mgr):
    normalizer = CollectionNormalizer()
    raw_html = b"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Safe Vendor Profile</title>
        <meta name="description" content="Vendor details">
        <script>alert('malicious js execution');</script>
        <style>body { color: red; }</style>
    </head>
    <body>
        <h1>Vendor Alpha</h1>
        <p>Reliable hardware vendor since 2024.</p>
        <a href="https://example.onion/orders">Orders</a>
        <iframe src="https://evil.onion/track"></iframe>
    </body>
    </html>
    """

    capture = temp_capture_mgr.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/vendor",
        raw_content_bytes=raw_html,
        status="succeeded",
        http_status=200,
    )

    payload = normalizer.normalize(capture, raw_content_bytes=raw_html)

    assert isinstance(payload, NormalizedPayload)
    assert payload.processing_status == ProcessingStatus.valid.value
    assert payload.title == "Safe Vendor Profile"
    assert "Vendor Alpha" in payload.extracted_text
    assert "alert" not in payload.extracted_text  # Script stripped!
    assert "body { color: red; }" not in payload.extracted_text  # Style stripped!
    assert len(payload.links) == 1
    assert payload.links[0]["href"] == "https://example.onion/orders"
    assert payload.raw_metadata["sha256"] == capture.sha256


def test_normalizer_quarantines_oversized_ec03(temp_capture_mgr):
    """EC-03: Payloads > 10MB must be quarantined, preserving raw metadata."""
    normalizer = CollectionNormalizer(max_response_bytes=10485760)

    # 10.5 MB payload
    oversized_bytes = b"A" * (10485760 + 512)

    capture = temp_capture_mgr.create_capture(
        source_id="fixture_market_b",
        url="fixture://market-b/oversized",
        raw_content_bytes=oversized_bytes,
        status="succeeded",
        http_status=200,
    )

    payload = normalizer.normalize(capture, raw_content_bytes=oversized_bytes)

    assert payload.processing_status == ProcessingStatus.quarantined.value
    assert "EC-03" in (payload.quarantine_reason or "")
    assert payload.extracted_text is None
    # Raw metadata must be preserved
    assert payload.raw_metadata["size_bytes"] == len(oversized_bytes)
    assert payload.raw_metadata["capture_id"] == capture.capture_id


def test_normalizer_quarantines_disallowed_mime_ec03(temp_capture_mgr):
    """EC-03: MIME types not in allowlist must be quarantined."""
    normalizer = CollectionNormalizer(mime_allowlist=["text/html", "application/json"])

    raw_bin = b"\x7fELF\x02\x01\x01\x00some_binary"
    capture = temp_capture_mgr.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/binary.bin",
        raw_content_bytes=raw_bin,
        status="succeeded",
        content_type="application/octet-stream",
    )

    payload = normalizer.normalize(capture, raw_content_bytes=raw_bin)

    assert payload.processing_status == ProcessingStatus.quarantined.value
    assert "EC-03" in (payload.quarantine_reason or "")
    assert payload.raw_metadata["capture_id"] == capture.capture_id


def test_normalizer_quarantines_binary_null_bytes_ec03(temp_capture_mgr):
    """EC-03: Binary content disguised as text/html must be quarantined."""
    normalizer = CollectionNormalizer()

    sneaky_payload = b"<html>\x00\x00\x01malicious_binary_shellcode</html>"
    capture = temp_capture_mgr.create_capture(
        source_id="fixture_market_a",
        url="fixture://market-a/sneaky.html",
        raw_content_bytes=sneaky_payload,
        status="succeeded",
        content_type="text/html",
    )

    payload = normalizer.normalize(capture, raw_content_bytes=sneaky_payload)

    assert payload.processing_status == ProcessingStatus.quarantined.value
    assert "Binary content or null bytes" in (payload.quarantine_reason or "")
