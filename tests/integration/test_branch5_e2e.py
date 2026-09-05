import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository


@pytest.fixture
def client(temp_db):
    return TestClient(create_app(db_path=temp_db))


def _hdr(client, role):
    tok = client.post("/api/v1/auth/token", json={"username": f"{role}_u", "role": role}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_branch5_search_profile_decision_audit(client, temp_db):
    # Seed an entity + candidate link
    EntityRepository(temp_db).save({"entity_id": "actor_a", "entity_type": "actor", "canonical_name": "GhostVendor"})
    LinkRepository(temp_db).save_candidate_link({
        "link_id": "link_ab", "left_entity_id": "actor_a", "right_entity_id": "actor_b",
        "state": "proposed", "score": 0.7, "tier": "likely_same_actor",
        "explanation": "shared pgp", "score_model_version": "v1.0", "calculation_input_hash": "h1",
    })

    # 1. Search finds the actor
    s = client.post("/api/v1/search", json={"query": "ghost"}, headers=_hdr(client, "viewer"))
    assert s.json()["total"] == 1

    # 2. Actor profile shows the candidate link with tier + disclosure
    prof = client.get("/api/v1/actors/actor_a", headers=_hdr(client, "viewer")).json()
    assert prof["found"] and prof["link_count"] == 1
    assert "does not defeat Tor" in prof["disclosure"]

    # 3. Viewer cannot make a decision (RBAC)
    denied = client.post("/api/v1/links/link_ab/transition",
                         json={"target_state": "needs_review", "reason": "look closer"},
                         headers=_hdr(client, "viewer"))
    assert denied.status_code == 403

    # 4. Analyst decision with mandatory reason succeeds
    ok = client.post("/api/v1/links/link_ab/transition",
                     json={"target_state": "needs_review", "reason": "corroborated by wallet"},
                     headers=_hdr(client, "analyst"))
    assert ok.status_code == 200

    # 5. Audit trail (reviewer) records the transition
    events = client.get("/api/v1/audit", headers=_hdr(client, "reviewer")).json()["events"]
    assert len(events) >= 1
