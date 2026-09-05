from graph.neo4j_projection import Neo4jProjection

def test_neo4j_projection_fallback_when_offline():
    # Attempt connecting to invalid host to test graceful fallback (EC-07)
    proj = Neo4jProjection(uri="bolt://127.0.0.1:9999", user="neo4j", password="bad")
    assert proj.is_connected is False

    # Operations still succeed using NetworkX fallback
    proj.add_node("Node_A", attributes={"label": "Persona"})
    proj.add_node("Node_B", attributes={"label": "Persona"})
    proj.add_edge("Node_A", "Node_B", link_id="link_ab", score=0.85, tier="likely_same_actor")

    p_data = proj.get_projection()
    assert p_data["node_count"] == 2
    assert p_data["edge_count"] == 1

    paths = proj.find_paths("Node_A", "Node_B")
    assert len(paths) == 1
    assert paths[0]["path_confidence"] == 0.85
