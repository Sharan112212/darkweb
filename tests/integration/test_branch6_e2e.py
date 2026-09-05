from db.repositories.link_repo import LinkRepository
from graph.networkx_projection import NetworkXProjection
from graph.path_finder import PathFinder

def test_branch6_end_to_end_graph_projection_and_attribution_path(temp_db):
    repo = LinkRepository(temp_db)

    # Seed 3 multi-hop candidate links
    links = [
        {
            "link_id": "l_hop_1",
            "left_entity_id": "GhostVendor_Profile",
            "right_entity_id": "Shared_PGP_Key_001",
            "state": "accepted",
            "score": 0.95,
            "tier": "observed_technical_identity",
            "score_model_version": "v1.0",
            "calculation_input_hash": "h1"
        },
        {
            "link_id": "l_hop_2",
            "left_entity_id": "Shared_PGP_Key_001",
            "right_entity_id": "Server_Infra_Node",
            "state": "accepted",
            "score": 0.80,
            "tier": "likely_same_actor",
            "score_model_version": "v1.0",
            "calculation_input_hash": "h2"
        },
        {
            "link_id": "l_hop_3",
            "left_entity_id": "Server_Infra_Node",
            "right_entity_id": "Nightshade99_Profile",
            "state": "needs_review",
            "score": 0.70,
            "tier": "likely_same_actor",
            "score_model_version": "v1.0",
            "calculation_input_hash": "h3"
        }
    ]

    for l in links:
        repo.save_candidate_link(l)

    proj = NetworkXProjection()
    synced = proj.sync_from_db(db_path=temp_db)
    assert synced == 3

    finder = PathFinder(projection=proj)
    analysis = finder.find_attribution_paths("GhostVendor_Profile", "Nightshade99_Profile", max_hops=4)

    assert analysis["paths_found"] == 1
    top = analysis["paths"][0]
    assert top["hops"] == 3
    # Confidence = 0.95 * 0.80 * 0.70 = 0.532
    assert abs(top["path_confidence"] - 0.532) < 0.01
    assert top["nodes"] == ["GhostVendor_Profile", "Shared_PGP_Key_001", "Server_Infra_Node", "Nightshade99_Profile"]
