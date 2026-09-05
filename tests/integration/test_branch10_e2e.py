import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.rbac import create_jwt_token
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository
from graph.reconciliation import GraphReconciliationEngine

def test_branch10_e2e_canonical_graph_pipeline(temp_db):
    # 1. Setup DB state
    entity_repo = EntityRepository(temp_db)
    link_repo = LinkRepository(temp_db)

    entity_repo.save({"entity_id": "actor_e2e_alpha", "entity_type": "Persona", "canonical_name": "Alpha"})
    entity_repo.save({"entity_id": "actor_e2e_beta", "entity_type": "Persona", "canonical_name": "Beta"})
    entity_repo.save({"entity_id": "actor_e2e_gamma", "entity_type": "Persona", "canonical_name": "Gamma"})

    link_repo.save_candidate_link({
        "link_id": "link_alpha_beta",
        "left_entity_id": "actor_e2e_alpha",
        "right_entity_id": "actor_e2e_beta",
        "state": "accepted",
        "score": 0.85,
        "tier": "likely_same_actor",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_ab"
    })
    link_repo.save_candidate_link({
        "link_id": "link_beta_gamma",
        "left_entity_id": "actor_e2e_beta",
        "right_entity_id": "actor_e2e_gamma",
        "state": "accepted",
        "score": 0.90,
        "tier": "observed_technical_identity",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_bg"
    })

    # 2. Backfill graph projection
    engine = GraphReconciliationEngine(db_path=temp_db)
    bf_res = engine.backfill()
    assert bf_res["nodes_synced"] == 3
    assert bf_res["edges_synced"] == 2

    # 3. Test API Endpoints
    app = create_app(db_path=temp_db)
    client = TestClient(app)

    viewer_token = create_jwt_token("viewer_alice", "viewer")
    admin_token = create_jwt_token("admin_boss", "admin")

    # GET /api/v1/actors/actor_e2e_alpha/graph
    subg_res = client.get(
        "/api/v1/actors/actor_e2e_alpha/graph?depth=2",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert subg_res.status_code == 200
    subg_data = subg_res.json()
    assert subg_data["node_count"] == 3
    assert subg_data["edge_count"] == 2
    assert subg_data["truncated"] is False

    # POST /api/v1/graph/paths
    paths_res = client.post(
        "/api/v1/graph/paths",
        json={"source_entity_id": "actor_e2e_alpha", "target_entity_id": "actor_e2e_gamma", "max_hops": 3},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert paths_res.status_code == 200
    p_data = paths_res.json()
    assert p_data["paths_found"] == 1
    assert p_data["highest_confidence"] == round(0.85 * 0.90, 4)

    # POST /api/v1/graph/reconcile (Admin only)
    rec_res = client.post(
        "/api/v1/graph/reconcile",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["reconciled"] is True

    # POST /api/v1/graph/rollback (Admin only)
    rb_res = client.post(
        "/api/v1/graph/rollback",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rb_res.status_code == 200
    assert rb_res.json()["status"] == "rolled_back_and_resynced"
