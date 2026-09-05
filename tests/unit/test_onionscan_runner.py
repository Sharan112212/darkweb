import os
import pytest
from scanners.onionscan_runner import OnionScanRunner, ScanStatus
from models.evidence import EvidenceUnit

FIX = "fixtures/onionscan"


# --------------------------------------------------------------- existing EC-07

def test_onionscan_runner_fixture_replay(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="ghostvendor.onion", target_entity="actor_ghostvendor")
    assert len(units) > 0
    for u in units:
        assert isinstance(u, EvidenceUnit)
        assert u.category == "I"
        assert u.source == "onionscan"
    assert runner.last_result["status"] == ScanStatus.SUCCESS


def test_onionscan_runner_missing_binary_fallback_ec07(tmp_path):
    runner = OnionScanRunner(onionscan_binary="nonexistent_onionscan_bin", mode="live",
                             raw_output_dir=str(tmp_path))
    units = runner.scan(target="nonexistent_target.onion", target_entity="actor_test")
    assert units == []  # EC-07: graceful scanner failure returns 0 evidence units
    assert runner.last_result["status"] == ScanStatus.ERROR


def test_onionscan_runner_missing_fixture_ec07(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="unknown_target_999.onion", target_entity="actor_test")
    assert units == []  # EC-07: zero evidence units on missing fixture


# --------------------------------------------------------- new: edge fixtures

def test_valid_fixture_parses_to_infra_evidence(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="valid_result.onion",
                        fixture_path=os.path.join(FIX, "valid_result.json"),
                        target_entity="actor_valid")
    assert len(units) > 0
    assert all(u.category == "I" for u in units)
    assert runner.last_result["status"] == ScanStatus.SUCCESS
    assert runner.last_result["raw_output_sha256"]  # raw hash stored


def test_timeout_fixture_safe_status_no_crash(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="timeout_result.onion",
                        fixture_path=os.path.join(FIX, "timeout_result.json"),
                        target_entity="actor_timeout")
    assert units == []
    assert runner.last_result["status"] == ScanStatus.TIMEOUT
    assert runner.last_result["raw_output_sha256"]  # raw preserved


def test_schema_change_fixture_marks_adapter_failure(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="schema_change.onion",
                        fixture_path=os.path.join(FIX, "schema_change.json"),
                        target_entity="actor_schema")
    assert units == []
    assert runner.last_result["status"] == ScanStatus.SCHEMA_ERROR
    assert runner.last_result["raw_output_sha256"]  # raw preserved for triage


def test_error_fixture_saved_and_pipeline_continues(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    units = runner.scan(target="error_result.onion",
                        fixture_path=os.path.join(FIX, "error_result.json"),
                        target_entity="actor_error")
    assert units == []
    assert runner.last_result["status"] == ScanStatus.ERROR
    # error artifact persisted
    assert runner.last_result["raw_output_path"] and os.path.isfile(runner.last_result["raw_output_path"])


# ---------------------------------------------------------- new: allowlist

def test_allowlist_blocks_unlisted_target_with_audit(tmp_path):
    events = []
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path),
                             allowlist=["ghostvendor.onion"], audit_sink=events.append)
    units = runner.scan(target="evil_unlisted.onion", target_entity="actor_evil")
    assert units == []
    assert runner.last_result["status"] == ScanStatus.BLOCKED
    assert len(events) == 1
    assert events[0]["event_type"] == "onionscan_scan_blocked"


def test_allowlist_permits_listed_target(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path),
                             allowlist=["ghostvendor.onion"])
    units = runner.scan(target="ghostvendor.onion", target_entity="actor_ghostvendor")
    assert len(units) > 0


# ------------------------------------------------------- new: raw hash stored

def test_raw_output_hash_stored_for_every_attempt(tmp_path):
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir=FIX, raw_output_dir=str(tmp_path))
    runner.scan(target="ghostvendor.onion", target_entity="actor_ghostvendor")
    meta = runner.last_result
    assert meta["raw_output_sha256"] and len(meta["raw_output_sha256"]) == 64
    assert os.path.isfile(meta["raw_output_path"])


def test_non_root_guard_defaults_to_disallow_root():
    runner = OnionScanRunner(mode="live")
    assert runner.allow_root is False
    assert runner.timeout_seconds == 120
    assert runner.max_output_bytes == 5 * 1024 * 1024
