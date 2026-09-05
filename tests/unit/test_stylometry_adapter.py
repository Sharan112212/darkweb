import json
import pytest
from pathlib import Path
from adapters.classical_stylometry_adapter import ClassicalStylometryAdapter

FIXTURES_DIR = Path("fixtures/stylometry")

def load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_stylometry_adapter_true_positive():
    adapter = ClassicalStylometryAdapter()
    data = load_fixture("true_positive_pair.json")

    units = adapter.extract(data)
    assert len(units) == 1

    unit = units[0]
    assert unit.category == "S"
    assert unit.indicator_type == "classical_stylometry"
    assert unit.confidence_weight <= 0.20  # Strictly capped at 0.20
    assert "Classical stylometry is supporting evidence only, capped at 0.20 contribution." in unit.limitations
    assert unit.linked_entities == ["author_alpha", "author_beta"]
    assert "corpus_hash" in unit.model_metadata

def test_stylometry_adapter_short_corpus_emits_no_evidence():
    adapter = ClassicalStylometryAdapter()
    data = load_fixture("short_corpus.json")

    units = adapter.extract(data)
    assert len(units) == 0  # No evidence emitted when gates fail

def test_stylometry_adapter_mixed_language_emits_no_evidence():
    adapter = ClassicalStylometryAdapter()
    data = load_fixture("mixed_language.json")

    units = adapter.extract(data)
    assert len(units) == 0  # No evidence emitted when language gate fails
