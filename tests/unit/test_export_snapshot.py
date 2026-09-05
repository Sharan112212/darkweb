import pytest
from export.exporter import ExportEngine

def test_export_snapshot_version_lock():
    exporter = ExportEngine()

    mutable_evidence = [{
        "evidence_id": "ev_001",
        "category": "K",
        "indicator_type": "pgp_fingerprint",
        "indicator_value": "ORIGINAL_VALUE",
        "confidence_weight": 0.95
    }]
    mutable_links = [{
        "link_id": "link_001",
        "left_entity_id": "actor_a",
        "right_entity_id": "actor_b",
        "score": 0.85,
        "tier": "likely_same_actor"
    }]

    # Create frozen snapshot
    snapshot = exporter.create_snapshot(
        generated_by="analyst_1",
        user_role="analyst",
        actors=[],
        candidate_links=mutable_links,
        evidence_units=mutable_evidence
    )

    # Mutate original objects after snapshot creation
    mutable_evidence[0]["indicator_value"] = "MUTATED_VALUE_AFTER_EXPORT"
    mutable_links[0]["score"] = 0.10

    # Render snapshot JSON
    rendered_json = exporter.render_json(snapshot)

    # Verify frozen snapshot retains ORIGINAL values
    assert "ORIGINAL_VALUE" in rendered_json
    assert "MUTATED_VALUE_AFTER_EXPORT" not in rendered_json
    assert snapshot.candidate_links[0]["score"] == 0.85
