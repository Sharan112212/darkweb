"""
Branch 9 audit tests (spec filename tests/test_audit.py): append-only behaviour
and tamper detection of the governance audit chain.
"""
from governance.audit import TamperEvidentAuditChain, AuditStore


def _chain():
    c = TamperEvidentAuditChain()
    c.append(request_id="r1", user_id="u1", user_role="analyst", action="VIEW_ENTITY", object_id="actor_a")
    c.append(request_id="r2", user_id="u1", user_role="analyst", action="ACCEPT_LINK", object_id="link_1")
    c.append(request_id="r3", user_id="u2", user_role="reviewer", action="CREATE_EXPORT", object_id="exp_1")
    return c


def test_audit_store_is_tamper_evident_chain_alias():
    assert AuditStore is TamperEvidentAuditChain


def test_append_only_accumulates_and_chains_hashes():
    c = _chain()
    events = c.list_events()
    assert len(events) == 3
    # each record chains to the previous one (append-only integrity)
    for i in range(1, len(events)):
        assert events[i].previous_event_hash == events[i - 1].event_hash
    assert events[0].event_hash and events[0].previous_event_hash


def test_clean_chain_verifies():
    ok, msg = _chain().verify_integrity()
    assert ok is True
    assert "verified" in msg.lower()


def test_tampering_a_record_is_detected():
    c = _chain()
    c.list_events()[1].details["x"] = "hacked"
    ok, msg = c.verify_integrity()
    assert ok is False
    assert "Integrity check failed" in msg


def test_filter_by_user_and_object():
    c = _chain()
    assert len(c.list_events(user_id="u1")) == 2
    assert len(c.list_events(object_id="exp_1")) == 1
