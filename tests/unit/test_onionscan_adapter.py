import json
import os
import pytest
from adapters.onionscan_adapter import (
    OnionScanAdapter,
    INFRA_CONFIDENCE_CAP,
    STALE_SCAN_DAYS,
    ONIONSCAN_ADAPTER_SCHEMA_VERSION,
)

FIX = "fixtures/onionscan"


def _load(name):
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as f:
        return json.load(f)


def test_valid_report_maps_to_capped_infra_evidence():
    adapter = OnionScanAdapter()
    units = adapter.extract(_load("valid_result.json"), target_entity="actor_valid")
    assert len(units) > 0
    for u in units:
        assert u.category == "I"
        assert u.confidence_weight <= INFRA_CONFIDENCE_CAP
        assert u.model_metadata["adapter_schema_version"] == ONIONSCAN_ADAPTER_SCHEMA_VERSION


def test_low_rarity_adds_caveat_and_downweights():
    adapter = OnionScanAdapter()
    units = adapter.extract(_load("valid_result.json"), target_entity="actor_valid", rarity=0.2)
    assert units
    u = units[0]
    assert u.model_metadata["rarity"] == 0.2
    assert any("Low-rarity" in lim or "shared hosting" in lim.lower() for lim in u.limitations)


def test_stale_scan_adds_caveat_and_lowers_time_confidence():
    adapter = OnionScanAdapter()
    units = adapter.extract(_load("valid_result.json"), target_entity="actor_valid",
                            scan_age_days=STALE_SCAN_DAYS + 30)
    assert units
    u = units[0]
    assert u.time_confidence <= 0.5
    assert any("Stale scan" in lim for lim in u.limitations)


def test_infra_cap_enforced_even_without_rarity():
    adapter = OnionScanAdapter()
    units = adapter.extract(_load("valid_result.json"), target_entity="actor_valid")
    assert all(u.confidence_weight <= INFRA_CONFIDENCE_CAP for u in units)
