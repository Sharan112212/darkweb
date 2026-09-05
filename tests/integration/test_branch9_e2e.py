import pytest
from cases.case_manager import CaseManager
from export.exporter import ExportEngine
from governance.audit import TamperEvidentAuditChain
from governance.redaction import RedactionEngine

def test_branch9_e2e_case_export_governance_pipeline():
    # 1. Create Case
    case_mgr = CaseManager()
    case = case_mgr.create_case(
        name="Operation GhostHunter",
        description="Investigation into GhostVendor marketplace rebrand",
        created_by="analyst_alpha",
        actor_ids=["actor_ghostvendor", "actor_nightshade99"],
        link_ids=["link_rebrand_001"],
        evidence_ids=["ev_pgp_001", "ev_beh_002"]
    )
    assert case.case_id.startswith("case_")

    # 2. Append Audit Log
    audit_store = TamperEvidentAuditChain()
    audit_store.append("req_101", "analyst_alpha", "analyst", "CREATE_CASE", case.case_id, {"case_name": case.name})
    audit_store.append("req_102", "analyst_alpha", "analyst", "ADD_NOTE", case.case_id, {"note": "Evidence verified."})

    # 3. Create Export Snapshot
    exporter = ExportEngine()
    actors = [{"entity_id": "actor_ghostvendor", "name": "GhostVendor"}]
    links = [{"link_id": "link_rebrand_001", "left_entity_id": "actor_ghostvendor", "right_entity_id": "actor_nightshade99", "score": 0.82, "tier": "likely_same_actor"}]
    evidence = [{"evidence_id": "ev_pgp_001", "category": "K", "indicator_type": "pgp_fingerprint", "indicator_value": "1122334455667788990011223344556677889900", "confidence_weight": 0.95, "explanation": "PGP key match"}]

    snapshot = exporter.create_snapshot(
        generated_by="analyst_alpha",
        user_role="analyst",
        actors=actors,
        candidate_links=links,
        evidence_units=evidence,
        case_id=case.case_id
    )

    # 4. Render Reports
    json_report = exporter.render_json(snapshot)
    csv_report = exporter.render_csv(snapshot)
    pdf_bytes = exporter.render_pdf(snapshot)

    assert "This system provides confidence-scored technical associations" in json_report
    assert "link_rebrand_001" in csv_report
    assert len(pdf_bytes) > 0

    # 5. Verify Audit Log Integrity
    is_valid, msg = audit_store.verify_integrity()
    assert is_valid is True
    assert len(audit_store.list_events()) == 2
