import pytest
from fastapi.testclient import TestClient
from api.app import create_app

@pytest.fixture
def client(temp_db):
    app = create_app(db_path=temp_db)
    return TestClient(app)

def test_auth_token_generation(client):
    res = client.post("/api/v1/auth/token", json={
        "username": "analyst_alice",
        "role": "analyst"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "analyst"
    assert data["user_id"] == "analyst_alice"

def test_auth_me_with_valid_token(client):
    # Get token
    token_res = client.post("/api/v1/auth/token", json={
        "username": "reviewer_bob",
        "role": "reviewer"
    })
    token = token_res.json()["access_token"]

    # Call /me
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["user_id"] == "reviewer_bob"
    assert user_data["role"] == "reviewer"

def test_auth_me_unauthorized(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
