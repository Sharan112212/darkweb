from adapters.minilm_evidence_adapter import MiniLMEvidenceAdapter
from models.enums import IndicatorType

def test_minilm_adapter_valid():
    adapter = MiniLMEvidenceAdapter()
    payload = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "similarity": 0.8590,
        "post_count_a": 10,
        "post_count_b": 12,
        "char_count_a": 2500,
        "char_count_b": 3000
    }

    units = adapter.extract(payload)
    assert len(units) == 1

    unit = units[0]
    assert unit.indicator_type == IndicatorType.semantic_similarity.value
    assert "supporting evidence only" in unit.limitations[0]

def test_minilm_adapter_gate_failure():
    adapter = MiniLMEvidenceAdapter()
    payload = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "similarity": 0.8590,
        "post_count_a": 2, # Gate failure (< 5 posts)
        "post_count_b": 12,
        "char_count_a": 500, # Gate failure (< 1500 chars)
        "char_count_b": 3000
    }

    units = adapter.extract(payload)
    assert len(units) == 0 # Must emit nothing on gate failure
