import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.rbac import create_jwt_token
from db.repositories.link_repo import LinkRepository

@pytest.fixture
def client_and_repo(temp_db):
    app = create_app(db_path=temp_db)
    repo = LinkRepository(temp_db)
    client = TestClient(app)
    return client, repo

def test_graph_api_endpoints(client_and_repo):
    client, repo = client_and_repo

    # Seed link
    link = {
        "link_id": "link_api_graph_1",
        "left_entity_id": "actor_alpha",
        "right_entity_id": "actor_beta",
        "state": "accepted",
        "score": 0.88,
        "tier": "likely_same_actor",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_graph_1"
    }
    repo.save_candidate_link(link)

    token = create_jwt_token("analyst_bob", "analyst")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Sync endpoint
    sync_res = client.post("/api/v1/graph/sync", headers=headers)
    assert sync_res.status_code == 200
    assert sync_res.json()["synced_edges"] >= 1

    # 2. Projection endpoint
    proj_res = client.get("/api/v1/graph/projection", headers=headers)
    assert proj_res.status_code == 200
    p_data = proj_res.json()
    assert p_data["node_count"] >= 2
    assert p_data["edge_count"] >= 1

    # 3. Paths endpoint
    paths_res = client.get(
        "/api/v1/graph/paths?source_entity_id=actor_alpha&target_entity_id=actor_beta",
        headers=headers
    )
    assert paths_res.status_code == 200
    p_result = paths_res.json()
    assert p_result["paths_found"] == 1
    assert p_result["highest_confidence"] == 0.88
