from datetime import datetime, timezone, timedelta
from adapters.infra_evidence_adapter import InfraEvidenceAdapter
from models.enums import IndicatorType

def test_infra_adapter_freshness_decay():
    adapter = InfraEvidenceAdapter()
    
    # Fresh observation (today)
    now_str = datetime.now(timezone.utc).isoformat()
    fresh_decay = adapter.calculate_freshness(now_str)
    assert fresh_decay == 1.0

    # Old observation (180 days ago = 1 half life)
    old_dt = datetime.now(timezone.utc) - timedelta(days=180)
    old_str = old_dt.isoformat()
    old_decay = adapter.calculate_freshness(old_str)
    assert 0.45 <= old_decay <= 0.55  # ~0.50

def test_infra_adapter_extract_with_decay_and_ec08_limitations():
    adapter = InfraEvidenceAdapter()
    old_dt = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
    
    payload = {
        "onion_address": "ghostvendor.onion",
        "clearnet_host": "ghostvendor.com",
        "evidence": "SHA-256: A1:B2:C3:D4:E5:F6:78:90:12:34:56:78:9A:BC:DE:F0:12:34:56:78:9A:BC:DE:F0:12:34:56:78:9A:BC:DE:F0",
        "observation_date": old_dt,
        "rarity": 0.80
    }

    units = adapter.extract(payload)
    assert len(units) == 1
    u = units[0]
    assert u.category == "I"
    assert u.indicator_type == IndicatorType.certificate_fingerprint.value
    # Base weight 0.80 * freshness ~0.50 * rarity 0.80 => ~0.32
    assert 0.20 <= u.confidence_weight <= 0.45
    assert any("EC-08" in lim for lim in u.limitations)
