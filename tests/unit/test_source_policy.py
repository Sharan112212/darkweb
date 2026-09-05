"""
Unit tests for Source Policy and Authorization Engine (Branch 2).
Tests allowlist enforcement, blocklist priority, kill switch, and authorization expiry (EC-05).
"""
from datetime import datetime, timezone, timedelta
from collection.capture_manager import CaptureManager


def test_source_allowlist_check(temp_db):
    """Test approved sources pass allowlist and unknown sources are rejected."""
    cm = CaptureManager(temp_db)
    # Known approved fixture source
    assert cm.is_source_allowlisted("fixture://market-a/ghostvendor.html") is True
    assert cm.is_source_allowlisted("fixture://market-b/mirror_ghostvendor.html") is True

    # Unapproved unknown onion source
    assert cm.is_source_allowlisted("http://unauthorized-unknown-darkmarket.onion/listing") is False


def test_source_blocklist_override(temp_db):
    """Test blocklist strictly overrides allowlist."""
    cm = CaptureManager(temp_db)
    # Blocklisted source in sources.yaml
    assert cm.is_source_allowlisted("fixture://blocked/captcha_page.html") is False

    status, reason = cm.check_authorization("fixture://blocked/captcha_page.html")
    assert status == "blocked"
    assert "blocklisted" in reason.lower()


def test_kill_switch_blocks_all_sources(temp_db):
    """Test global collection kill switch halts all collection immediately."""
    cm = CaptureManager(temp_db)
    assert cm.is_source_allowlisted("fixture://market-a/ghostvendor.html") is True

    # Activate kill switch
    cm.policy["kill_switch"] = True
    assert cm.is_source_allowlisted("fixture://market-a/ghostvendor.html") is False
    assert cm.is_source_allowlisted("fixture://market-b/mirror_ghostvendor.html") is False

    status, reason = cm.check_authorization("fixture://market-a/ghostvendor.html")
    assert status == "blocked"
    assert "kill switch" in reason.lower()


def test_source_authorization_expiry_ec05(temp_db):
    """Test expired source authorization is detected and blocked per EC-05."""
    cm = CaptureManager(temp_db)
    past_expiry = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    # Add expired source definition
    cm.sources.append({
        "id": "expired_market",
        "url_pattern": "fixture://expired-market/*",
        "mode": "fixture_replay",
        "authorization_status": "approved",
        "expires_at": past_expiry,
        "blocklisted": False,
    })

    status, reason = cm.check_authorization("fixture://expired-market/items.html", source_id="expired_market")
    assert status == "expired"
    assert "expired" in reason.lower()
    assert cm.is_source_allowlisted("fixture://expired-market/items.html", source_id="expired_market") is False


def test_check_authorization_contract(temp_db):
    """Test check_authorization returns structured (status, reason) tuple."""
    cm = CaptureManager(temp_db)
    status, reason = cm.check_authorization("fixture://market-a/ghostvendor.html")
    assert status == "approved"
    assert reason is None
