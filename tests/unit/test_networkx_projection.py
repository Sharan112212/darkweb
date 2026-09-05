from graph.networkx_projection import NetworkXProjection
from db.repositories.link_repo import LinkRepository

def test_networkx_projection_basic(temp_db):
    repo = LinkRepository(temp_db)

    # Seed 3-hop chain: Actor A -> Actor B -> Actor C -> Actor D
    link1 = {
        "link_id": "link_ab",
        "left_entity_id": "Actor_A",
        "right_entity_id": "Actor_B",
        "state": "accepted",
        "score": 0.90,
        "tier": "observed_technical_identity",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_ab"
    }
    link2 = {
        "link_id": "link_bc",
        "left_entity_id": "Actor_B",
        "right_entity_id": "Actor_C",
        "state": "accepted",
        "score": 0.80,
        "tier": "likely_same_actor",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_bc"
    }
    link3 = {
        "link_id": "link_cd",
        "left_entity_id": "Actor_C",
        "right_entity_id": "Actor_D",
        "state": "proposed",
        "score": 0.50,
        "tier": "possible_association",
        "score_model_version": "v1.0",
        "calculation_input_hash": "hash_cd"
    }

    repo.save_candidate_link(link1)
    repo.save_candidate_link(link2)
    repo.save_candidate_link(link3)

    proj = NetworkXProjection()
    count = proj.sync_from_db(db_path=temp_db)
    assert count == 3

    p_data = proj.get_projection()
    assert p_data["node_count"] == 4
    assert p_data["edge_count"] == 3

    # Find paths from Actor_A to Actor_D
    paths = proj.find_paths("Actor_A", "Actor_D", max_hops=4)
    assert len(paths) == 1
    path = paths[0]
    assert path["hops"] == 3
    assert path["nodes"] == ["Actor_A", "Actor_B", "Actor_C", "Actor_D"]
    # Aggregated path confidence: 0.90 * 0.80 * 0.50 = 0.36
    assert abs(path["path_confidence"] - 0.36) < 0.01
