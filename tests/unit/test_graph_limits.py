import pytest
from graph.networkx_projection import NetworkXProjection

def test_graph_limits_date_range_and_depth():
    proj = NetworkXProjection()

    # Create chain of nodes: A -> B -> C -> D
    proj.add_node("node_A")
    proj.add_node("node_B")
    proj.add_node("node_C")
    proj.add_node("node_D")

    proj.add_edge("node_A", "node_B", link_id="link_AB", score=0.9, tier="likely_same_actor", attributes={"created_at": "2026-01-01T00:00:00Z"})
    proj.add_edge("node_B", "node_C", link_id="link_BC", score=0.8, tier="likely_same_actor", attributes={"created_at": "2026-02-01T00:00:00Z"})
    proj.add_edge("node_C", "node_D", link_id="link_CD", score=0.7, tier="possible_association", attributes={"created_at": "2026-03-01T00:00:00Z"})

    # 1. Depth cutoff: depth=1 from node_A should only reach node_B
    sg_depth1 = proj.get_subgraph("node_A", depth=1)
    assert sg_depth1["node_count"] == 2
    assert set(n["id"] for n in sg_depth1["nodes"]) == {"node_A", "node_B"}
    assert sg_depth1["truncated"] is False

    # 2. Date filtering: date_to="2026-01-15T00:00:00Z" should filter out B->C link
    sg_date = proj.get_subgraph("node_A", depth=3, date_to="2026-01-15T00:00:00Z")
    assert set(n["id"] for n in sg_date["nodes"]) == {"node_A", "node_B"}

    # 3. Limit truncation: setting limit=2 when 4 nodes exist
    sg_trunc = proj.get_subgraph("node_A", depth=3, limit=2)
    assert sg_trunc["node_count"] == 2
    assert sg_trunc["truncated"] is True
