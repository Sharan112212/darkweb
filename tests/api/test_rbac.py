import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.rbac import create_jwt_token

@pytest.fixture
def client(temp_db):
    app = create_app(db_path=temp_db)
    return TestClient(app)

def test_viewer_role_cannot_transition_link(client):
    viewer_token = create_jwt_token("viewer_user", "viewer")
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Attempt mutation endpoint
    res = client.post(
        "/api/v1/links/link_001/transition",
        headers=headers,
        json={"target_state": "accepted", "reason": "Attempted viewer edit"}
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]

def test_analyst_role_can_access_mutation(client):
    analyst_token = create_jwt_token("analyst_user", "analyst")
    headers = {"Authorization": f"Bearer {analyst_token}"}

    # Calling transition on non-existent link returns 400 or 404 (not 403 Forbidden)
    res = client.post(
        "/api/v1/links/nonexistent_link/transition",
        headers=headers,
        json={"target_state": "accepted", "reason": "Valid analyst role"}
    )
    assert res.status_code in [400, 404, 500]  # Passes RBAC auth, fails on link lookup
