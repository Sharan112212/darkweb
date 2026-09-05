import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from db.repositories.timeline_repo import TimelineRepository


@pytest.fixture
def client(temp_db):
    app = create_app(db_path=temp_db)
    return TestClient(app)


def _token(client, role="viewer"):
    res = client.post("/api/v1/auth/token", json={"username": f"{role}_u", "role": role})
    return res.json()["access_token"]


def _seed(temp_db):
    repo = TimelineRepository(temp_db)
    repo.append({"event_id": "tl_1", "event_type": "pgp_seen", "entity_id": "actor_a",
                 "timestamp": "2026-06-01T00:00:00+00:00", "description": "pgp", "evidence_ids": ["ev_1"]})
    repo.append({"event_id": "tl_2", "event_type": "wallet_seen", "entity_id": "actor_a",
                 "timestamp": "2026-07-01T00:00:00+00:00", "description": "wallet", "evidence_ids": ["ev_2"]})
    repo.append({"event_id": "tl_3", "event_type": "candidate_link_created", "entity_id": "actor_a",
                 "timestamp": "2026-08-01T00:00:00+00:00", "description": "link", "evidence_ids": []})


def test_timeline_requires_auth(client):
    assert client.get("/api/v1/actors/actor_a/timeline").status_code == 401


def test_timeline_returns_events(client, temp_db):
    _seed(temp_db)
    token = _token(client)
    res = client.get("/api/v1/actors/actor_a/timeline", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert data["timezone"] == "UTC"
    assert len(data["events"]) == 3


def test_timeline_date_filter(client, temp_db):
    _seed(temp_db)
    token = _token(client)
    res = client.get("/api/v1/actors/actor_a/timeline",
                     params={"from": "2026-06-15T00:00:00+00:00", "to": "2026-07-15T00:00:00+00:00"},
                     headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    assert data["total"] == 1
    assert data["events"][0]["event_id"] == "tl_2"


def test_timeline_pagination_truncated_flag(client, temp_db):
    _seed(temp_db)
    token = _token(client)
    res = client.get("/api/v1/actors/actor_a/timeline", params={"limit": 2, "offset": 0},
                     headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    assert data["returned"] == 2
    assert data["truncated"] is True
    assert data["total"] == 3


def test_timeline_empty_has_explicit_absence_reason(client, temp_db):
    token = _token(client)
    res = client.get("/api/v1/actors/nobody/timeline", headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    assert data["total"] == 0
    assert data["events"] == []
    assert data["absence_reason"] == "no_timeline_events"
