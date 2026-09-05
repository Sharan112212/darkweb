import pytest
from graph.networkx_projection import NetworkXProjection
from graph.path_finder import PathFinder

def test_path_finder_multi_hop_attribution():
    proj = NetworkXProjection()
    proj.add_edge("GhostVendor", "Persona_X", link_id="l1", score=0.90, tier="observed_technical_identity")
    proj.add_edge("Persona_X", "Nightshade99", link_id="l2", score=0.80, tier="likely_same_actor")

    finder = PathFinder(projection=proj)
    res = finder.find_attribution_paths("GhostVendor", "Nightshade99", max_hops=4)

    assert res["paths_found"] == 1
    assert res["source_entity"] == "GhostVendor"
    assert res["target_entity"] == "Nightshade99"
    assert abs(res["highest_confidence"] - 0.72) < 0.01  # 0.90 * 0.80 = 0.72
    assert "Found 1 attribution path" in res["summary"]

def test_path_finder_no_path():
    proj = NetworkXProjection()
    proj.add_node("Isolated_A")
    proj.add_node("Isolated_B")

    finder = PathFinder(projection=proj)
    res = finder.find_attribution_paths("Isolated_A", "Isolated_B")
    assert res["paths_found"] == 0
    assert res["highest_confidence"] == 0.0
