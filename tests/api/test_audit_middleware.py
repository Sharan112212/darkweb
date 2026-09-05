import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.rbac import create_jwt_token
from db.repositories.audit_repo import AuditRepository

@pytest.fixture
def client_and_audit(temp_db):
    app = create_app(db_path=temp_db)
    client = TestClient(app)
    audit_repo = AuditRepository(temp_db)
    return client, audit_repo

def test_audit_middleware_logs_requests(client_and_audit):
    client, audit_repo = client_and_audit

    token = create_jwt_token("audited_user", "analyst")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/links", headers=headers)
    assert res.status_code == 200

    events = audit_repo.list_events()
    assert len(events) > 0
    actions = [e.get("action") for e in events]
    assert any("GET /api/v1/links" in act for act in actions)
