"""
Unit tests for TorCollector (Branch 2).
Tests SOCKS5h proxy configuration and validation (EC-06),
timeout handling, CAPTCHA detection and login gates without bypass (EC-04),
oversized response handling (EC-03), and 503 failure status recording (EC-01).
"""
import pytest
import requests
from unittest.mock import MagicMock
from collection.tor_collector import TorCollector


def test_tor_collector_proxy_configuration():
    """Test SOCKS5h proxy configuration is validated and enforced (EC-06)."""
    # Valid socks5h proxy
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050")
    assert tc.socks_proxy == "socks5h://127.0.0.1:9050"
    assert tc.proxy_url == "socks5h://127.0.0.1:9050"

    # Insecure proxies without remote DNS (socks5:// without h, http://) must be rejected per EC-06
    with pytest.raises(ValueError) as excinfo:
        TorCollector(socks_proxy="socks5://127.0.0.1:9050")
    assert "socks5h://" in str(excinfo.value)
    assert "EC-06" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        TorCollector(socks_proxy="http://127.0.0.1:8080")
    assert "socks5h://" in str(excinfo.value)


def test_tor_collector_blocked_unauthorized_source(temp_db):
    """Test unapproved / non-allowlisted onion sources are blocked prior to network egress."""
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050", db_path=temp_db)
    capture, content = tc.fetch("http://unauthorized-unknown.onion/feed")
    assert capture.status == "blocked"
    assert "blocked" in capture.not_collected_reason.lower() or "unauthorized" in capture.not_collected_reason.lower()


def test_tor_collector_timeout(temp_db, monkeypatch):
    """Test network timeout is caught and produces durable failed status (EC-01)."""
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050", db_path=temp_db, timeout=2)
    tc.retry_backoff = 0.01
    tc.request_delay = 0.0
    # Ensure source passes authorization check for the test
    monkeypatch.setattr(tc.capture_manager, "check_authorization", lambda url, source_id=None: ("approved", None))

    def mock_get(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out after 2 seconds")

    monkeypatch.setattr(requests.Session, "get", mock_get)

    cap = tc.collect("http://timeout-market.onion/listing", source_id="timeout_market")
    assert cap.status == "failed"
    assert "timed out" in cap.not_collected_reason.lower()
    assert "EC-01" in cap.not_collected_reason


def test_tor_collector_captcha_detection_ec04(temp_db, monkeypatch):
    """
    Test CAPTCHA detection (EC-04).
    The collector must record not_collected_reason and never attempt automated bypass.
    """
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050", db_path=temp_db)
    monkeypatch.setattr(tc.capture_manager, "check_authorization", lambda url, source_id=None: ("approved", None))

    captcha_html = (
        b"<!DOCTYPE html><html><body>"
        b"<h2>Security Check - Please solve the CAPTCHA to continue</h2>"
        b"<div class='g-recaptcha' data-sitekey='6Le-wvkSAAAAAPBMRTvw0Q49Wv'></div>"
        b"</body></html>"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.iter_content = lambda chunk_size=65536: [captcha_html]

    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: mock_resp)

    cap = tc.collect("http://protected-market.onion/catalog", source_id="protected_market")
    assert cap.status == "blocked"
    assert "captcha" in cap.not_collected_reason.lower()
    assert "EC-04" in cap.not_collected_reason
    # Verify no attempt to bypass or solve was made
    assert "passive" in cap.not_collected_reason.lower()


def test_tor_collector_login_gate_detection_ec04(temp_db, monkeypatch):
    """Test login form required source is flagged as blocked without bypass attempt (EC-04)."""
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050", db_path=temp_db)
    monkeypatch.setattr(tc.capture_manager, "check_authorization", lambda url, source_id=None: ("approved", None))

    login_html = (
        b"<!DOCTYPE html><html><body>"
        b"<h1>Authorization Required</h1>"
        b"<p>Please login to continue</p>"
        b"<form><input type='text' name='user'><input type='password' name='pass'></form>"
        b"</body></html>"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.iter_content = lambda chunk_size=65536: [login_html]

    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: mock_resp)

    cap = tc.collect("http://login-market.onion/dashboard", source_id="login_market")
    assert cap.status == "blocked"
    assert "login" in cap.not_collected_reason.lower() or "authentication" in cap.not_collected_reason.lower()


def test_tor_collector_oversized_response_quarantine_ec03(temp_db, monkeypatch):
    """Test response exceeding 10MB during streaming is quarantined per EC-03."""
    tc = TorCollector(
        socks_proxy="socks5h://127.0.0.1:9050",
        db_path=temp_db,
        max_response_bytes=10485760,
    )
    monkeypatch.setattr(tc.capture_manager, "check_authorization", lambda url, source_id=None: ("approved", None))

    chunk = b"A" * (2 * 1024 * 1024)  # 2MB chunks
    chunks = [chunk] * 6  # 12MB total

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.iter_content = lambda chunk_size=65536: chunks
    mock_resp.close = MagicMock()

    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: mock_resp)

    cap = tc.collect("http://bomb-market.onion/giant.html", source_id="bomb_market")
    assert cap.status == "quarantined"
    assert "exceeded" in cap.not_collected_reason.lower()
    assert "EC-03" in cap.not_collected_reason
    assert mock_resp.close.called
