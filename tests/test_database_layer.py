"""
Comprehensive integration test suite for the database layer and repository pattern.
Tests SQLite connection, schema migration, idempotency constraints, and all repositories.
"""

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db.connection import get_connection
from db.migrations import run_migration
from db.repositories import (
    AuditRepository,
    CaptureRepository,
    EntityRepository,
    EvidenceRepository,
    LinkRepository,
    TimelineRepository,
)


class TestDatabaseLayer(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite database for isolated testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        run_migration(self.temp_db_path)
        self.conn = get_connection(self.temp_db_path)

        # Repositories
        self.capture_repo = CaptureRepository(connection=self.conn)
        self.evidence_repo = EvidenceRepository(connection=self.conn)
        self.link_repo = LinkRepository(connection=self.conn)
        self.audit_repo = AuditRepository(connection=self.conn)
        self.entity_repo = EntityRepository(connection=self.conn)
        self.timeline_repo = TimelineRepository(connection=self.conn)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_captures_repository(self):
        """Test CaptureRepository save, retrieval, and idempotency."""
        capture_data = {
            "capture_id": "cap_test_001",
            "source_id": "fixture_market_a",
            "url": "fixture://market-a/profile/ghostvendor",
            "mode": "fixture_replay",
            "authorization_status": "approved",
            "captured_at": "2026-09-05T10:00:00Z",
            "source_claimed_time": "2026-09-01T08:00:00Z",
            "http_status": 200,
            "content_type": "text/html",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "raw_object_reference": "fixtures/market-a/ghostvendor.html",
            "status": "succeeded",
            "not_collected_reason": None,
        }

        saved = self.capture_repo.save(capture_data)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["capture_id"], "cap_test_001")
        self.assertEqual(saved["source_id"], "fixture_market_a")

        # Retrieve by ID
        fetched = self.capture_repo.get_by_id("cap_test_001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["sha256"], capture_data["sha256"])

        # Test idempotency: saving duplicate unique key (source_id, url, sha256, captured_at)
        duplicate_data = dict(capture_data)
        duplicate_data["capture_id"] = "cap_test_002_different_id"
        duplicate_saved = self.capture_repo.save(duplicate_data)
        self.assertEqual(duplicate_saved["capture_id"], "cap_test_001")

        # List all
        all_caps = self.capture_repo.list_all()
        self.assertEqual(len(all_caps), 1)

    def test_evidence_repository(self):
        """Test EvidenceRepository save, get_by_id, list_by_pair, list_all, and idempotency."""
        # 1. First save capture
        self.capture_repo.save({
            "capture_id": "cap_001",
            "source_id": "market_alpha",
            "url": "http://alpha.onion/actor1",
            "mode": "tor_proxy",
            "authorization_status": "approved",
            "captured_at": "2026-09-05T12:00:00Z",
            "status": "succeeded",
        })

        # 2. Save Evidence Unit
        ev_data = {
            "evidence_id": "ev_test_101",
            "schema_version": "1.0",
            "capture_id": "cap_001",
            "source": "market_alpha",
            "source_version": "1.0",
            "indicator_type": "crypto_wallet",
            "indicator_value": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "indicator_role": "deposit_address",
            "left_entity_id": "actor_ghost",
            "right_entity_id": "actor_phantom",
            "confidence_weight": 0.95,
            "source_reliability": 0.85,
            "extraction_confidence": 0.90,
            "limitations_json": ["Blockchain cluster heuristic supporting only"],
            "model_metadata_json": {"model": "wallet_extractor_v1"},
            "explanation": "Identical Bitcoin deposit address shared in profile footer",
        }

        saved = self.evidence_repo.save(ev_data)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["evidence_id"], "ev_test_101")
        self.assertIn("limitations", saved)
        self.assertIsInstance(saved["limitations_json"], list)
        self.assertIsInstance(saved["model_metadata_json"], dict)

        # 3. Retrieve by ID
        fetched = self.evidence_repo.get_by_id("ev_test_101")
        self.assertEqual(fetched["indicator_value"], ev_data["indicator_value"])

        # 4. Retrieve by pair (both directions)
        pairs_forward = self.evidence_repo.list_by_pair("actor_ghost", "actor_phantom")
        self.assertEqual(len(pairs_forward), 1)
        pairs_reverse = self.evidence_repo.list_by_pair("actor_phantom", "actor_ghost")
        self.assertEqual(len(pairs_reverse), 1)

        # 5. Idempotency Constraint Test:
        # UNIQUE(source, source_version, capture_id, indicator_type, indicator_value, left_entity_id, right_entity_id)
        dup_ev = dict(ev_data)
        dup_ev["evidence_id"] = "ev_different_id"
        dup_ev["explanation"] = "Should return existing record instead"
        dup_result = self.evidence_repo.save(dup_ev)
        self.assertEqual(dup_result["evidence_id"], "ev_test_101")
        self.assertEqual(self.evidence_repo.count(), 1)

    def test_link_repository_and_versions(self):
        """Test LinkRepository candidate link creation, automatic versioning, and idempotency."""
        link_data = {
            "link_id": "lnk_alpha_beta",
            "left_entity_id": "actor_ghost",
            "right_entity_id": "actor_phantom",
            "state": "needs_review",
            "score": 0.78,
            "tier": "probable_attribution",
            "score_status": "fused",
            "category_breakdown": {
                "K": {"score": 0.0, "state": "not_available"},
                "I": {"score": 0.65, "state": "observed"},
                "B": {"score": 0.85, "state": "observed"},
                "S": {"score": 0.72, "state": "observed"},
            },
            "evidence_ids": ["ev_test_101"],
            "explanation": "Multi-vector match across PGP key and Stylometry.",
            "limitations": ["Infrastructure signal not available."],
            "score_model_version": "scoring-v1.0",
            "calculation_input_hash": "sha256:abcd1234efgh5678",
            "changed_by": "fusion_pipeline",
            "reason": "Automated pipeline run",
        }

        # 1. Save new candidate link
        saved_link = self.link_repo.save_candidate_link(link_data)
        self.assertIsNotNone(saved_link)
        self.assertEqual(saved_link["link_id"], "lnk_alpha_beta")
        self.assertEqual(saved_link["link_version"], 1)
        self.assertEqual(saved_link["state"], "needs_review")
        self.assertIsInstance(saved_link["category_breakdown_json"], dict)

        # 2. Check that version record was automatically created
        versions = self.link_repo.get_versions("lnk_alpha_beta")
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["link_version"], 1)
        self.assertEqual(versions[0]["changed_by"], "fusion_pipeline")

        # 3. Test Idempotency: exact same entity pair + model version + calculation input hash
        dup_link = dict(link_data)
        dup_link["link_id"] = "lnk_different_id"
        dup_result = self.link_repo.save_candidate_link(dup_link)
        self.assertEqual(dup_result["link_id"], "lnk_alpha_beta")
        self.assertEqual(dup_result["link_version"], 1)
        self.assertEqual(len(self.link_repo.get_versions("lnk_alpha_beta")), 1)

        # 4. Test Version bump on modification
        update_data = dict(link_data)
        update_data["state"] = "confirmed"
        update_data["score"] = 0.82
        update_data["calculation_input_hash"] = "sha256:new_hash_9999"
        update_data["changed_by"] = "analyst_alice"
        update_data["reason"] = "Analyst confirmed shared PGP key match"

        updated = self.link_repo.save_candidate_link(update_data)
        self.assertEqual(updated["link_version"], 2)
        self.assertEqual(updated["state"], "confirmed")
        self.assertEqual(updated["score"], 0.82)

        # Verify version records now contain 2 snapshots
        versions_after = self.link_repo.get_versions("lnk_alpha_beta")
        self.assertEqual(len(versions_after), 2)
        self.assertEqual(versions_after[0]["link_version"], 1)
        self.assertEqual(versions_after[0]["state"], "needs_review")
        self.assertEqual(versions_after[1]["link_version"], 2)
        self.assertEqual(versions_after[1]["state"], "confirmed")
        self.assertEqual(versions_after[1]["changed_by"], "analyst_alice")

        # 5. Retrieve by pair
        by_pair = self.link_repo.get_by_pair("actor_phantom", "actor_ghost")
        self.assertIsNotNone(by_pair)
        self.assertEqual(by_pair["link_id"], "lnk_alpha_beta")

    def test_audit_repository(self):
        """Test AuditRepository append-only logging and idempotency."""
        event_data = {
            "event_id": "aud_001",
            "request_id": "req_user_action_123",
            "user_id": "analyst_bob",
            "action": "confirm_link",
            "object_id": "lnk_alpha_beta",
            "timestamp": "2026-09-05T14:30:00Z",
            "details_json": {"note": "Strong correlation confirmed via GPG fingerprint"},
        }

        saved = self.audit_repo.append(event_data)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["event_id"], "aud_001")
        self.assertEqual(saved["user_id"], "analyst_bob")

        # Retrieve by ID
        fetched = self.audit_repo.get_by_id("aud_001")
        self.assertEqual(fetched["action"], "confirm_link")
        self.assertEqual(fetched["details_json"]["note"], "Strong correlation confirmed via GPG fingerprint")

        # Test Idempotency: duplicate request_id, action, object_id, timestamp
        dup_event = dict(event_data)
        dup_event["event_id"] = "aud_002_duplicate"
        dup_result = self.audit_repo.append(dup_event)
        self.assertEqual(dup_result["event_id"], "aud_001")
        self.assertEqual(self.audit_repo.count(), 1)

        # List events with filter
        events = self.audit_repo.list_events(object_id="lnk_alpha_beta")
        self.assertEqual(len(events), 1)

    def test_entity_repository(self):
        """Test EntityRepository creation, lookup, and normalization."""
        ent = {
            "entity_id": "ent_ghostvendor",
            "entity_type": "threat_actor",
            "canonical_name": "GhostVendor",
            "display_name": "Ghost Vendor (AlphaBay)",
            "normalized_name": "ghostvendor",
            "category": "malware_author",
        }
        saved = self.entity_repo.save(ent)
        self.assertEqual(saved["entity_id"], "ent_ghostvendor")

        # Lookup by canonical and normalized names
        by_canon = self.entity_repo.get_by_canonical_name("GhostVendor")
        self.assertIsNotNone(by_canon)
        self.assertEqual(by_canon["entity_id"], "ent_ghostvendor")

        by_norm = self.entity_repo.get_by_normalized_name("GHOSTVENDOR")
        self.assertIsNotNone(by_norm)
        self.assertEqual(by_norm["entity_id"], "ent_ghostvendor")

    def test_timeline_repository(self):
        """Test TimelineRepository event creation and chronologic ordering."""
        self.timeline_repo.append({
            "event_id": "tl_1",
            "event_type": "first_seen",
            "entity_id": "ent_ghostvendor",
            "timestamp": "2026-09-01T10:00:00Z",
            "time_confidence": "exact",
            "description": "First observed listing on DarkMarket Alpha",
            "evidence_ids_json": ["ev_101"],
            "metadata_json": {"source": "forum_post"},
        })
        self.timeline_repo.append({
            "event_id": "tl_2",
            "event_type": "pgp_key_registered",
            "entity_id": "ent_ghostvendor",
            "timestamp": "2026-09-02T12:00:00Z",
            "time_confidence": "exact",
            "description": "Registered PGP key fingerprint",
            "evidence_ids_json": ["ev_102"],
        })

        events = self.timeline_repo.list_by_entity("ent_ghostvendor")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_id"], "tl_1")
        self.assertEqual(events[1]["event_id"], "tl_2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
