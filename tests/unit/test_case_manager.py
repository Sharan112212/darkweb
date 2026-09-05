from cases.case_manager import CaseManager

def test_case_manager_crud_and_references():
    cm = CaseManager()
    case = cm.create_case(
        name="Operation DarkNet",
        description="Attribution investigation for vendor GhostVendor",
        created_by="analyst_alpha",
        actor_ids=["actor_ghostvendor"],
        link_ids=["link_12345"],
        evidence_ids=["ev_pgp_999"]
    )

    assert case.case_id.startswith("case_")
    assert case.name == "Operation DarkNet"
    assert case.status == "open"
    assert case.legal_hold is False
    assert "actor_ghostvendor" in case.actor_ids
    assert "link_12345" in case.link_ids

    # Add items by reference
    cm.add_actor(case.case_id, "actor_nightshade99", "analyst_alpha")
    cm.add_link(case.case_id, "link_67890", "analyst_alpha")
    cm.add_evidence(case.case_id, "ev_cert_888", "analyst_alpha")

    updated = cm.get_case(case.case_id)
    assert "actor_nightshade99" in updated.actor_ids
    assert "link_67890" in updated.link_ids
    assert "ev_cert_888" in updated.evidence_ids

    # Add note
    cm.add_note(case.case_id, "analyst_alpha", "Found shared PGP signature correlation.")
    assert len(updated.notes) == 1
    assert updated.notes[0].text == "Found shared PGP signature correlation."

    # Update status & legal hold
    cm.update_status(case.case_id, "under_review", "reviewer_beta")
    cm.set_legal_hold(case.case_id, True, "reviewer_beta")

    final_case = cm.get_case(case.case_id)
    assert final_case.status == "under_review"
    assert final_case.legal_hold is True
