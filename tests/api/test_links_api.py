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

def test_link_lifecycle_api_end_to_end(client_and_repo):
    client, repo = client_and_repo

    # Seed initial candidate link
    link_data = {
        "link_id": "link_test_api_100",
        "link_version": 1,
        "left_entity_id": "actor_ghostvendor",
        "right_entity_id": "actor_nightshade99",
        "state": "proposed",
        "score": 0.95,
        "tier": "observed_technical_identity",
        "score_status": "observed",
        "category_breakdown": {"K": 1.0},
        "evidence_ids": ["ev_001"],
        "explanation": "Test link for API transition",
        "score_model_version": "scoring-v1.0",
        "calculation_input_hash": "hash_test_100",
        "created_at": "2026-09-05T10:00:00Z",
        "updated_at": "2026-09-05T10:00:00Z"
    }
    repo.save_candidate_link(link_data)

    analyst_token = create_jwt_token("analyst_bob", "analyst")
    headers = {"Authorization": f"Bearer {analyst_token}"}

    # 1. Get link by ID
    get_res = client.get("/api/v1/links/link_test_api_100", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["state"] == "proposed"

    # 2. Transition state proposed -> needs_review
    trans_res = client.post(
        "/api/v1/links/link_test_api_100/transition",
        headers=headers,
        json={"target_state": "needs_review", "reason": "Analyst flag for peer review"}
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["state"] == "needs_review"
    assert trans_res.json()["link_version"] == 2

    # 3. Check history endpoint
    hist_res = client.get("/api/v1/links/link_test_api_100/history", headers=headers)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 2
