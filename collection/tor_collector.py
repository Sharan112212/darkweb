"""
Hardened SOCKS5h Tor Collector for SIH26151 Dark-Web Attribution Platform.
Enforces:
- socks5h:// proxy exclusively (remote DNS over Tor to prevent clearnet DNS leaks per EC-06).
- Strict timeouts, 10MB response size cap, request pacing delay, and per-host concurrency of 1.
- Passive collection only: never executes JavaScript, never submits forms, never solves CAPTCHA (EC-04).
- Failure and status recording via CaptureManager (EC-01).
"""

import os
import re
import threading
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from collection.capture_manager import CaptureManager
from models.capture import Capture


class TorCollector:
    """
    Hardened Tor collector wrapper for passive, safe intelligence harvesting.
    Strictly forbids JavaScript execution, form submission, and CAPTCHA solving.
    """

    # Indicators of CAPTCHA challenges or login-only gates
    CAPTCHA_PATTERNS = [
        re.compile(r"g-recaptcha", re.IGNORECASE),
        re.compile(r"h-captcha", re.IGNORECASE),
        re.compile(r"cf-turnstile", re.IGNORECASE),
        re.compile(r"name=[\"']captcha", re.IGNORECASE),
        re.compile(r"solve\s+the\s+captcha", re.IGNORECASE),
        re.compile(r"security\s+check", re.IGNORECASE),
        re.compile(r"ddos\s+protection\s+by\s+cloudflare", re.IGNORECASE),
        re.compile(r"cf-browser-verification", re.IGNORECASE),
        re.compile(r"checking\s+your\s+browser", re.IGNORECASE),
        re.compile(r"just\s+a\s+moment\.\.\.", re.IGNORECASE),
        re.compile(r"please\s+verify\s+you\s+are\s+human", re.IGNORECASE),
    ]

    LOGIN_PATTERNS = [
        re.compile(r"<input[^>]+type=[\"']password[\"']", re.IGNORECASE),
        re.compile(r"please\s+login\s+to\s+continue", re.IGNORECASE),
        re.compile(r"authorization\s+required", re.IGNORECASE),
    ]

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        socks_proxy: Optional[str] = None,
        capture_manager: Optional[CaptureManager] = None,
        db_path: Optional[str] = None,
        timeout: Optional[int] = None,
        max_response_bytes: Optional[int] = None,
        request_delay_seconds: Optional[float] = None,
    ):
        if db_path and not capture_manager:
            self.capture_manager = CaptureManager(db_path=db_path)
        else:
            self.capture_manager = capture_manager or CaptureManager()
        policy = self.capture_manager.policy

        # Resolve proxy URL with strict socks5h validation (EC-06)
        raw_proxy = socks_proxy or proxy_url or os.environ.get("TOR_SOCKS_PROXY", "socks5h://127.0.0.1:9050")
        self.proxy_url = self._validate_and_format_proxy(raw_proxy)
        self.socks_proxy = self.proxy_url

        # Operational parameters from policy
        self.timeout = timeout or policy.get("default_timeout_seconds", 30)
        self.max_response_bytes = max_response_bytes or policy.get("max_response_bytes", 10485760)
        self.request_delay = (
            request_delay_seconds
            if request_delay_seconds is not None
            else float(policy.get("request_delay_seconds", 2.0))
        )
        self.max_retries = int(policy.get("max_retries", 2))
        self.retry_backoff = float(policy.get("retry_backoff_seconds", 5.0))

        # Concurrency & pacing locks per host
        self._host_locks: Dict[str, threading.Lock] = {}
        self._host_lock_global = threading.Lock()
        self._last_request_time: Dict[str, float] = {}

    def _validate_and_format_proxy(self, proxy_url: str) -> str:
        """
        Forces socks5h:// scheme. Rejects any socks5:// or http:// scheme that would
        risk DNS leakage to clearnet resolvers (EC-06).
        """
        p = proxy_url.strip()
        if not p.startswith("socks5h://"):
            raise ValueError(
                f"Insecure proxy scheme '{p}'. Tor collector strictly requires 'socks5h://' "
                "to enforce remote DNS resolution over Tor and prevent clearnet egress leaks (EC-06)."
            )
        return p

    def _get_host_lock(self, hostname: str) -> threading.Lock:
        """Returns or creates the concurrency lock for a specific hostname (per-host concurrency 1)."""
        with self._host_lock_global:
            if hostname not in self._host_locks:
                self._host_locks[hostname] = threading.Lock()
            return self._host_locks[hostname]

    def _apply_request_pacing(self, hostname: str) -> None:
        """Enforces request_delay_seconds between requests to the same host."""
        last_time = self._last_request_time.get(hostname, 0.0)
        elapsed = time.time() - last_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time[hostname] = time.time()

    def detect_passive_blocking(self, content_str: str) -> Tuple[bool, Optional[str]]:
        """
        Detects if content is a CAPTCHA gate, DDoS protection screen, or login-only page.
        Enforces EC-04: Never attempt to solve or bypass.
        """
        for pattern in self.CAPTCHA_PATTERNS:
            if pattern.search(content_str):
                return True, "CAPTCHA / challenge detected; passive collection only per EC-04"

        for pattern in self.LOGIN_PATTERNS:
            if pattern.search(content_str):
                return True, "Authentication / login required; passive collection only per EC-04"

        return False, None

    def fetch(self, url: str, source_id: Optional[str] = None) -> Tuple[Capture, bytes]:
        """
        Fetches an onion/target URL, returning (Capture, content_bytes).
        """
        src_id = source_id or "tor_source"
        if not self.capture_manager.is_source_allowlisted(url, source_id=src_id):
            error_bytes = b"Source blocked by policy"
            capture = self.capture_manager.create_capture(
                source_id=src_id,
                url=url,
                raw_content_bytes=error_bytes,
                status="blocked",
                http_status=403,
                not_collected_reason="Source blocked by policy",
                mode="authorized_tor",
            )
            return capture, error_bytes
        cap = self.collect(url, source_id=src_id)
        return cap, b""

    def collect(
        self,
        url: str,
        source_id: str,
        session: Optional[requests.Session] = None,
    ) -> Capture:
        """
        Collects an onion/target URL over hardened Tor proxy:
        - Checks source authorization first.
        - Enforces per-host lock and rate-limiting delay.
        - Streams response up to max_response_bytes (10MB).
        - Passively inspects for CAPTCHA/login without executing JS or solving (EC-04).
        - Handles retries and failure persistence via CaptureManager (EC-01).
        """
        # 1. Authorization check
        auth_status, auth_reason = self.capture_manager.check_authorization(url, source_id=source_id)
        if auth_status != "approved":
            return self.capture_manager.create_capture(
                source_id=source_id,
                url=url,
                raw_content_bytes=None,
                status="blocked",
                http_status=None,
                not_collected_reason=auth_reason or "Source unauthorized",
                mode="authorized_tor",
            )

        parsed_url = urlparse(url)
        hostname = parsed_url.netloc or parsed_url.path.split("/")[0]
        host_lock = self._get_host_lock(hostname)

        proxies = {
            "http": self.proxy_url,
            "https": self.proxy_url,
        }

        # Passive headers: mimic standard browser headers, no automated bypass signals
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        with host_lock:
            self._apply_request_pacing(hostname)

            attempt = 0
            last_error: Optional[Exception] = None

            while attempt <= self.max_retries:
                attempt += 1
                try:
                    client = session or requests.Session()
                    response = client.get(
                        url,
                        proxies=proxies,
                        headers=headers,
                        timeout=self.timeout,
                        stream=True,
                    )

                    http_status = response.status_code
                    content_type = response.headers.get("Content-Type", "text/html")

                    # Stream response content with size cap enforcement (EC-03)
                    content_chunks = []
                    total_bytes = 0
                    oversized = False

                    for chunk in response.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if total_bytes > self.max_response_bytes:
                            oversized = True
                            response.close()
                            break
                        content_chunks.append(chunk)

                    raw_content = b"".join(content_chunks)

                    if oversized:
                        return self.capture_manager.create_capture(
                            source_id=source_id,
                            url=url,
                            raw_content_bytes=raw_content,
                            status="quarantined",
                            http_status=http_status,
                            not_collected_reason=(
                                f"Response exceeded max allowed size of {self.max_response_bytes} bytes (EC-03)"
                            ),
                            content_type=content_type,
                            mode="authorized_tor",
                        )

                    # Check for server-side errors (503 / 504 / 500)
                    if http_status >= 500:
                        return self.capture_manager.create_capture(
                            source_id=source_id,
                            url=url,
                            raw_content_bytes=raw_content,
                            status="failed",
                            http_status=http_status,
                            not_collected_reason=f"Server returned HTTP {http_status} (EC-01)",
                            content_type=content_type,
                            mode="authorized_tor",
                        )

                    # Passive check for CAPTCHA or login wall (EC-04)
                    sample_text = raw_content[:32768].decode("utf-8", errors="ignore")
                    is_blocked, block_reason = self.detect_passive_blocking(sample_text)

                    if is_blocked:
                        return self.capture_manager.create_capture(
                            source_id=source_id,
                            url=url,
                            raw_content_bytes=raw_content,
                            status="blocked",
                            http_status=http_status,
                            not_collected_reason=block_reason,
                            content_type=content_type,
                            mode="authorized_tor",
                        )

                    # Successful passive capture
                    return self.capture_manager.create_capture(
                        source_id=source_id,
                        url=url,
                        raw_content_bytes=raw_content,
                        status="succeeded",
                        http_status=http_status,
                        not_collected_reason=None,
                        content_type=content_type,
                        mode="authorized_tor",
                    )

                except requests.exceptions.Timeout as exc:
                    last_error = exc
                    if attempt <= self.max_retries:
                        time.sleep(self.retry_backoff)
                        continue
                    return self.capture_manager.create_capture(
                        source_id=source_id,
                        url=url,
                        raw_content_bytes=None,
                        status="failed",
                        http_status=None,
                        not_collected_reason=f"Connection timed out after {self.timeout}s (EC-01)",
                        mode="authorized_tor",
                    )

                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt <= self.max_retries:
                        time.sleep(self.retry_backoff)
                        continue
                    return self.capture_manager.create_capture(
                        source_id=source_id,
                        url=url,
                        raw_content_bytes=None,
                        status="failed",
                        http_status=None,
                        not_collected_reason=f"Network/proxy error: {str(exc)} (EC-01)",
                        mode="authorized_tor",
                    )

                except Exception as exc:
                    last_error = exc
                    return self.capture_manager.create_capture(
                        source_id=source_id,
                        url=url,
                        raw_content_bytes=None,
                        status="failed",
                        http_status=None,
                        not_collected_reason=f"Unexpected collection error: {str(exc)}",
                        mode="authorized_tor",
                    )

            # If loop ends without return
            return self.capture_manager.create_capture(
                source_id=source_id,
                url=url,
                raw_content_bytes=None,
                status="failed",
                http_status=None,
                not_collected_reason=f"Retries exhausted: {str(last_error)}",
                mode="authorized_tor",
            )
