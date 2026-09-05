from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from models.enums import IndicatorType, IndicatorRole

def test_identity_adapter_pgp_normalization():
    adapter = IdentityEvidenceAdapter()
    raw = "9a3f 21b4 77c0 ee12 5d6a  8f90 11c3 4b22 fa01 9d77"
    norm = adapter.normalize_pgp_fingerprint(raw)
    assert norm == "9A3F21B477C0EE125D6A8F9011C34B22FA019D77"

def test_identity_adapter_extraction():
    adapter = IdentityEvidenceAdapter()
    payload = {
        "actor_a": "DarkFox",
        "actor_b": "DarkFox_v2",
        "evidence": "PGP Fingerprint: 9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77; Wallet Address: bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6o7p8a9",
        "signature_verified": False
    }

    units = adapter.extract(payload)
    assert len(units) == 2

    pgp_unit = [u for u in units if u.indicator_type == IndicatorType.pgp_fingerprint.value][0]
    wallet_unit = [u for u in units if u.indicator_type == IndicatorType.wallet_address.value][0]

    assert pgp_unit.indicator_role == IndicatorRole.key_published.value
    assert "Published key is not proof of key control" in pgp_unit.limitations[0]
    assert wallet_unit.indicator_role == IndicatorRole.wallet_unknown.value
    assert pgp_unit.linked_entities == ["DarkFox", "DarkFox_v2"]
