import pytest
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository
from graph.reconciliation import GraphReconciliationEngine
from graph.networkx_projection import NetworkXProjection

def test_graph_reconciliation_backfill_and_reconcile(temp_db):
    entity_repo = EntityRepository(temp_db)
    link_repo = LinkRepository(temp_db)

    # Seed entities
    entity_repo.save({"entity_id": "actor_rec_1", "entity_type": "Persona", "canonical_name": "Rec1"})
    entity_repo.save({"entity_id": "actor_rec_2", "entity_type": "Persona", "canonical_name": "Rec2"})

    # Seed candidate link
    link = {
        "link_id": "link_rec_12",
        "left_entity_id": "actor_rec_1",
        "right_entity_id": "actor_rec_2",
        "state": "accepted",
        "score": 0.92,
        "tier": "observed_technical_identity",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_rec_12"
    }
    link_repo.save_candidate_link(link)

    graph_proj = NetworkXProjection()
    engine = GraphReconciliationEngine(db_path=temp_db, graph_projection=graph_proj)

    # Backfill canonical DB into graph
    bf_res = engine.backfill()
    assert bf_res["status"] == "completed"
    assert bf_res["nodes_synced"] == 2
    assert bf_res["edges_synced"] == 1

    # Reconcile check
    rec_res = engine.reconcile()
    assert rec_res["reconciled"] is True
    assert rec_res["missing_entities_count"] == 0
    assert rec_res["missing_links_count"] == 0
    assert rec_res["canonical"]["entities_count"] == 2
    assert rec_res["canonical"]["links_count"] == 1

def test_graph_reconciliation_rollback(temp_db):
    entity_repo = EntityRepository(temp_db)
    link_repo = LinkRepository(temp_db)

    entity_repo.save({"entity_id": "actor_rb_1", "entity_type": "Persona", "canonical_name": "RB1"})
    entity_repo.save({"entity_id": "actor_rb_2", "entity_type": "Persona", "canonical_name": "RB2"})

    link = {
        "link_id": "link_rb_12",
        "left_entity_id": "actor_rb_1",
        "right_entity_id": "actor_rb_2",
        "state": "accepted",
        "score": 0.75,
        "tier": "likely_same_actor",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_rb_12"
    }
    link_repo.save_candidate_link(link)

    engine = GraphReconciliationEngine(db_path=temp_db)
    
    # Rollback rebuilds projection from canonical database cleanly
    rb_res = engine.rollback()
    assert rb_res["status"] == "rolled_back_and_resynced"
    assert rb_res["reconciliation"]["reconciled"] is True
