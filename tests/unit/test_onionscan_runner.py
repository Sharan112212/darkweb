import pytest
import os
from scanners.onionscan_runner import OnionScanRunner
from models.evidence import EvidenceUnit

def test_onionscan_runner_fixture_replay():
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir="fixtures/onionscan")
    units = runner.scan(target="ghostvendor.onion", target_entity="actor_ghostvendor")
    assert len(units) > 0
    for u in units:
        assert isinstance(u, EvidenceUnit)
        assert u.category == "I"
        assert u.source == "onionscan"

def test_onionscan_runner_missing_binary_fallback_ec07(monkeypatch):
    # Simulate missing binary and non-existent fixture
    runner = OnionScanRunner(onionscan_binary="nonexistent_onionscan_bin", mode="live")
    units = runner.scan(target="nonexistent_target.onion", target_entity="actor_test")
    assert units == []  # EC-07: Graceful scanner failure returns 0 evidence units

def test_onionscan_runner_missing_fixture_ec07():
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir="fixtures/onionscan")
    units = runner.scan(target="unknown_target_999.onion", target_entity="actor_test")
    assert units == []  # EC-07: Zero evidence units on missing fixture
