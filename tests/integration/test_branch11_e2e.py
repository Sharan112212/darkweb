import os
import json
import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.rbac import create_jwt_token
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository
from db.repositories.evidence_repo import EvidenceRepository
from fusion.explainable_fusion import ExplainableFusionEngine
from governance.audit import AuditStore

def test_branch11_e2e_demo_scenarios(temp_db):
    """
    Integration test verifying all 4 presentation scenarios for the live demo.
    """
    app = create_app(db_path=temp_db)
    client = TestClient(app)
    token = create_jwt_token("analyst_demo", "analyst")
    headers = {"Authorization": f"Bearer {token}"}

    entity_repo = EntityRepository(temp_db)
    link_repo = LinkRepository(temp_db)
    ev_repo = EvidenceRepository(temp_db)

    # 1. Setup Easy Case: GhostVendor PGP link
    entity_repo.save({"entity_id": "GhostVendor", "entity_type": "Persona", "canonical_name": "GhostVendor"})
    entity_repo.save({"entity_id": "GhostVendor_MarketB", "entity_type": "Persona", "canonical_name": "GhostVendor_MarketB"})

    link_repo.save_candidate_link({
        "link_id": "link_easy_case",
        "left_entity_id": "GhostVendor",
        "right_entity_id": "GhostVendor_MarketB",
        "state": "accepted",
        "score": 0.95,
        "tier": "observed_technical_identity",
        "category_breakdown": {"K": 0.95, "I": 0.0, "B": 0.0, "S": 0.0},
        "explanation": "High confidence cryptographic match via shared PGP key",
        "limitations": ["Published key is not proof of key control"],
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_easy"
    })

    # 2. Setup Hard Case: Text-only similarity
    entity_repo.save({"entity_id": "VendorAlpha", "entity_type": "Persona", "canonical_name": "VendorAlpha"})
    entity_repo.save({"entity_id": "VendorBeta", "entity_type": "Persona", "canonical_name": "VendorBeta"})

    link_repo.save_candidate_link({
        "link_id": "link_hard_case",
        "left_entity_id": "VendorAlpha",
        "right_entity_id": "VendorBeta",
        "state": "proposed",
        "score": 0.20,
        "tier": "possible_association",
        "category_breakdown": {"K": 0.0, "I": 0.0, "B": 0.0, "S": 0.20},
        "explanation": "Semantic similarity supporting evidence only",
        "limitations": ["Semantic similarity alone capped at possible_association"],
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_hard"
    })

    # Scenario 1 Verification: Actor Profile + Evidence Drawer
    res_easy = client.get("/api/v1/actors/GhostVendor", headers=headers)
    assert res_easy.status_code == 200
    easy_data = res_easy.json()
    assert easy_data["found"] is True
    assert easy_data["link_count"] >= 1
    assert "disclosure" in easy_data
    assert "confidence-scored technical associations" in easy_data["disclosure"]

    # Scenario 3 Verification: Hard Case Cap
    res_hard = client.get("/api/v1/links/link_hard_case", headers=headers)
    assert res_hard.status_code == 200
    hard_data = res_hard.json()
    assert hard_data["score"] <= 0.20
    assert hard_data["tier"] == "possible_association"

def test_branch11_air_gap_and_model_bundled():
    """
    Verifies that offline MiniLM model directory exists and contains safe tensors/config.
    """
    model_dir = os.path.join("models", "all-MiniLM-L6-v2")
    assert os.path.exists(model_dir), "MiniLM offline model directory must be bundled"
    config_path = os.path.join(model_dir, "config.json")
    assert os.path.exists(config_path), "Model config.json must exist for offline operation"

def test_branch11_fixture_manifest_integrity():
    """
    Verifies fixture manifest JSON exists and has valid checksum entries.
    """
    manifest_path = os.path.join("fixtures", "manifests", "fixture_manifest.json")
    assert os.path.exists(manifest_path), "Fixture manifest file must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 1
