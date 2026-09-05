from adapters.infra_evidence_adapter import InfraEvidenceAdapter
from models.enums import IndicatorType

def test_infra_adapter_extraction():
    adapter = InfraEvidenceAdapter()
    payload = {
        "onion_address": "vulnerable_service.onion",
        "clearnet_host": "techcorp-cloud.example",
        "evidence": "SHA-256: 4A:2B:3C:4D:5E:6F:70:81:92:A3:B4:C5:D6:E7:F8:09:10:11:12:13:14:15:16:17:18:19:1A:1B:1C:1D:1E:1F",
        "freshness": 0.90,
        "rarity": 0.85
    }

    units = adapter.extract(payload)
    assert len(units) == 1

    unit = units[0]
    assert unit.indicator_type == IndicatorType.certificate_fingerprint.value
    assert unit.indicator_value == "4a2b3c4d5e6f708192a3b4c5d6e7f809101112131415161718191a1b1c1d1e1f"
    assert unit.confidence_weight == 0.77 # 0.90 * 0.85 = 0.765 -> 0.77
    assert any("shared hosting" in lim for lim in unit.limitations)
