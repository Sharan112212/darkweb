import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository


@pytest.fixture
def client(temp_db):
    return TestClient(create_app(db_path=temp_db))


def _token(client, role):
    return client.post("/api/v1/auth/token", json={"username": f"{role}_u", "role": role}).json()["access_token"]


def _hdr(client, role="viewer"):
    return {"Authorization": f"Bearer {_token(client, role)}"}


def _seed(temp_db):
    er = EntityRepository(temp_db)
    er.save({"entity_id": "actor_a", "entity_type": "actor", "canonical_name": "GhostVendor"})
    er.save({"entity_id": "actor_b", "entity_type": "actor", "canonical_name": "Nightshade99"})
    lr = LinkRepository(temp_db)
    lr.save_candidate_link({
        "link_id": "link_ab", "left_entity_id": "actor_a", "right_entity_id": "actor_b",
        "state": "proposed", "score": 0.7, "tier": "likely_same_actor",
        "explanation": "shared pgp", "score_model_version": "v1.0", "calculation_input_hash": "h1",
    })


# ---------------------------------------------------------------- search
def test_search_returns_matches(client, temp_db):
    _seed(temp_db)
    r = client.post("/api/v1/search", json={"query": "ghost"}, headers=_hdr(client))
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_search_empty_has_absence_reason(client, temp_db):
    r = client.post("/api/v1/search", json={"query": "zzz"}, headers=_hdr(client))
    assert r.json()["total"] == 0
    assert r.json()["absence_reason"] in ("no_entities_collected", "no_matching_evidence")


# ---------------------------------------------------------------- entities
def test_list_and_get_entity(client, temp_db):
    _seed(temp_db)
    assert len(client.get("/api/v1/entities", headers=_hdr(client)).json()) == 2
    r = client.get("/api/v1/entities/actor/actor_a", headers=_hdr(client))
    assert r.status_code == 200 and r.json()["entity_id"] == "actor_a"
    assert client.get("/api/v1/entities/actor/missing", headers=_hdr(client)).status_code == 404


# ---------------------------------------------------------------- actors
def test_actor_profile_summary(client, temp_db):
    _seed(temp_db)
    r = client.get("/api/v1/actors/actor_a", headers=_hdr(client))
    data = r.json()
    assert data["found"] is True
    assert data["link_count"] == 1
    assert data["links"][0]["tier"] == "likely_same_actor"
    assert "disclosure" in data


def test_actor_profile_absent(client, temp_db):
    data = client.get("/api/v1/actors/nobody", headers=_hdr(client)).json()
    assert data["found"] is False
    assert data["absence_reason"] == "no_data_for_actor"


# ---------------------------------------------------------------- audit (RBAC)
def test_audit_requires_reviewer(client, temp_db):
    assert client.get("/api/v1/audit", headers=_hdr(client, "viewer")).status_code == 403
    assert client.get("/api/v1/audit", headers=_hdr(client, "analyst")).status_code == 403
    assert client.get("/api/v1/audit", headers=_hdr(client, "reviewer")).status_code == 200


# ---------------------------------------------------------------- admin (RBAC)
def test_admin_sources_admin_only(client, temp_db):
    assert client.get("/api/v1/admin/sources", headers=_hdr(client, "analyst")).status_code == 403
    r = client.get("/api/v1/admin/sources", headers=_hdr(client, "admin"))
    assert r.status_code == 200 and r.json()["count"] >= 1


def test_kill_switch_toggle_and_audit(client, temp_db):
    r = client.post("/api/v1/admin/kill-switch", json={"enabled": True, "reason": "incident"},
                    headers=_hdr(client, "admin"))
    assert r.status_code == 200 and r.json()["kill_switch"] is True
    # audited: reviewer can see the event
    events = client.get("/api/v1/audit", params={"action": "kill_switch_toggle"},
                        headers=_hdr(client, "reviewer")).json()["events"]
    assert any(e["action"] == "kill_switch_toggle" for e in events)


# ---------------------------------------------------------------- cases
def test_case_create_requires_analyst_and_title(client, temp_db):
    assert client.post("/api/v1/cases", json={"title": "X"}, headers=_hdr(client, "viewer")).status_code == 403
    assert client.post("/api/v1/cases", json={"title": "  "}, headers=_hdr(client, "analyst")).status_code == 400
    r = client.post("/api/v1/cases", json={"title": "Op GhostVendor"}, headers=_hdr(client, "analyst"))
    assert r.status_code == 200
    cid = r.json()["case_id"]
    assert client.get(f"/api/v1/cases/{cid}", headers=_hdr(client)).status_code == 200


def test_case_note_mandatory(client, temp_db):
    cid = client.post("/api/v1/cases", json={"title": "C"}, headers=_hdr(client, "analyst")).json()["case_id"]
    assert client.post(f"/api/v1/cases/{cid}/notes", json={"text": ""}, headers=_hdr(client, "analyst")).status_code == 400
    r = client.post(f"/api/v1/cases/{cid}/notes", json={"text": "reviewed"}, headers=_hdr(client, "analyst"))
    assert r.status_code == 200


# ---------------------------------------------------------------- exports
def test_export_snapshot_has_hash_and_disclosure(client, temp_db):
    _seed(temp_db)
    r = client.post("/api/v1/exports", json={"export_type": "links"}, headers=_hdr(client, "analyst"))
    assert r.status_code == 200
    exp = r.json()
    assert exp["snapshot_sha256"] and len(exp["snapshot_sha256"]) == 64
    assert "does not defeat Tor" in exp["disclosure"]
    # retrievable
    assert client.get(f"/api/v1/exports/{exp['export_id']}", headers=_hdr(client)).status_code == 200


def test_export_is_immutable_snapshot(client, temp_db):
    _seed(temp_db)
    exp = client.post("/api/v1/exports", json={"export_type": "links"}, headers=_hdr(client, "analyst")).json()
    # add a new link AFTER export
    LinkRepository(temp_db).save_candidate_link({
        "link_id": "link_new", "left_entity_id": "actor_a", "right_entity_id": "actor_c",
        "state": "proposed", "score": 0.5, "tier": "unresolved",
        "explanation": "x", "score_model_version": "v1.0", "calculation_input_hash": "h2",
    })
    again = client.get(f"/api/v1/exports/{exp['export_id']}", headers=_hdr(client)).json()
    # snapshot unchanged (immutable)
    assert again["snapshot_sha256"] == exp["snapshot_sha256"]
