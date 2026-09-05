import json
import pytest
from export.exporter import ExportEngine

def test_export_engine_snapshot_and_render_formats():
    exporter = ExportEngine()

    actors = [{"entity_id": "actor_a", "canonical_name": "GhostVendor"}]
    links = [{
        "link_id": "link_101",
        "left_entity_id": "actor_a",
        "right_entity_id": "actor_b",
        "score": 0.85,
        "tier": "likely_same_actor",
        "state": "proposed",
        "calculation_input_hash": "hash123"
    }]
    evidence = [{
        "evidence_id": "ev_001",
        "category": "K",
        "indicator_type": "pgp_fingerprint",
        "indicator_value": "1122334455667788990011223344556677889900",
        "confidence_weight": 0.95,
        "independence_group_id": "indep_pgp_1",
        "explanation": "Shared PGP fingerprint",
        "limitations": ["Published key is not proof of key control."]
    }]

    snapshot = exporter.create_snapshot(
        generated_by="analyst_1",
        user_role="analyst",
        actors=actors,
        candidate_links=links,
        evidence_units=evidence,
        case_id="case_123"
    )

    assert snapshot.export_id.startswith("exp_")
    assert snapshot.generated_by == "analyst_1"
    assert len(snapshot.candidate_links) == 1
    assert "This system provides confidence-scored technical associations" in snapshot.disclaimer

    # Test JSON rendering
    json_str = exporter.render_json(snapshot)
    parsed = json.loads(json_str)
    assert parsed["export_id"] == snapshot.export_id
    assert parsed["disclaimer"] == snapshot.disclaimer

    # Test CSV rendering
    csv_str = exporter.render_csv(snapshot)
    assert "SIH26151 Threat Actor Attribution Platform" in csv_str
    assert "link_101" in csv_str
    assert "ev_001" in csv_str

    # Test PDF rendering
    pdf_bytes = exporter.render_pdf(snapshot)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
