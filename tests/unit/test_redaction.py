import pytest
from governance.redaction import RedactionEngine

def test_redaction_engine_viewer_vs_analyst():
    engine = RedactionEngine()

    raw_evidence = {
        "evidence_id": "ev_pgp_123",
        "category": "K",
        "indicator_type": "pgp_fingerprint",
        "indicator_value": "1122334455667788990011223344556677889900",
        "confidence_weight": 0.95,
        "context_excerpt": "Raw forum post excerpt containing secret text",
        "raw_evidence_reference": "fixtures/market-a/ghostvendor.html",
        "limitations": []
    }

    # Test viewer role redaction
    viewer_result = engine.sanitize_evidence_unit(raw_evidence, user_role="viewer")
    assert viewer_result["is_redacted"] is True
    assert "[REDACTED FOR ROLE: viewer]" in viewer_result["indicator_value"]
    assert viewer_result["context_excerpt"] == "[REDACTED - ACCESS RESTRICTED FOR ROLE: viewer]"
    assert viewer_result["raw_evidence_reference"] == "[REDACTED - ACCESS RESTRICTED FOR ROLE: viewer]"

    # Test analyst role (unredacted)
    analyst_result = engine.sanitize_evidence_unit(raw_evidence, user_role="analyst")
    assert analyst_result["is_redacted"] is False
    assert analyst_result["indicator_value"] == "1122334455667788990011223344556677889900"
    assert analyst_result["context_excerpt"] == "Raw forum post excerpt containing secret text"

    # Test permissions helper
    assert engine.can_export_raw_evidence("viewer") is False
    assert engine.can_export_raw_evidence("analyst") is True
    assert engine.can_make_decision("viewer") is False
    assert engine.can_make_decision("analyst") is True
