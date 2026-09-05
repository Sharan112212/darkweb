import json
from pathlib import Path
from adapters.classical_stylometry_adapter import ClassicalStylometryAdapter
from adapters.minilm_evidence_adapter import MiniLMEvidenceAdapter
from fusion.explainable_fusion import ExplainableFusionEngine

FIXTURES_DIR = Path("fixtures/stylometry")

def load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_branch8_e2e_stylometry_to_fusion_pipeline():
    # 1. Load true positive stylometry fixture
    data = load_fixture("true_positive_pair.json")

    # 2. Extract classical stylometry evidence
    stylometry_adapter = ClassicalStylometryAdapter()
    style_units = stylometry_adapter.extract(data)
    assert len(style_units) == 1

    # 3. Extract MiniLM evidence
    minilm_adapter = MiniLMEvidenceAdapter()
    minilm_data = {
        "actor_a": data["actor_a"],
        "actor_b": data["actor_b"],
        "similarity": 0.85,
        "post_count_a": len(data["posts_a"]),
        "post_count_b": len(data["posts_b"]),
        "char_count_a": 2000,
        "char_count_b": 2000
    }
    minilm_units = minilm_adapter.extract(minilm_data)
    assert len(minilm_units) == 1

    # 4. Fuse both text-only signals in Fusion Engine
    fusion_engine = ExplainableFusionEngine()
    combined_evidence = style_units + minilm_units
    link = fusion_engine.evaluate_pair("author_alpha", "author_beta", combined_evidence)

    # 5. Verify text-only caps: score cannot exceed possible_association threshold
    assert link.score <= 0.65
    assert link.tier in ["possible_association", "unresolved", "insufficient_evidence"]
    assert "text" in link.explanation.lower() or "stylometry" in link.explanation.lower() or "semantic" in link.explanation.lower()
