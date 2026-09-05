from governance.audit import TamperEvidentAuditChain

def test_tamper_evident_audit_chain_verification():
    chain = TamperEvidentAuditChain()

    rec1 = chain.append(request_id="req_1", user_id="user_1", user_role="analyst", action="VIEW_ENTITY", object_id="actor_a")
    rec2 = chain.append(request_id="req_2", user_id="user_1", user_role="analyst", action="ACCEPT_LINK", object_id="link_101")
    rec3 = chain.append(request_id="req_3", user_id="user_2", user_role="reviewer", action="CREATE_EXPORT", object_id="exp_001")

    assert len(chain.list_events()) == 3
    is_valid, msg = chain.verify_integrity()
    assert is_valid is True
    assert "verified" in msg.lower()

    # Tamper with rec2 details
    rec2.details["tampered_key"] = "hacked_value"
    is_valid_after_tamper, tamper_msg = chain.verify_integrity()

    assert is_valid_after_tamper is False
    assert "Integrity check failed" in tamper_msg
