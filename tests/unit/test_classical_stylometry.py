import json
import pytest
from pathlib import Path
from analysis.classical_stylometry import ClassicalStylometryEngine

FIXTURES_DIR = Path("fixtures/stylometry")

@pytest.fixture
def engine():
    return ClassicalStylometryEngine()

def load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_true_positive_pair(engine):
    data = load_fixture("true_positive_pair.json")
    result = engine.analyze_pair(data["posts_a"], data["posts_b"])

    assert result["is_eligible"] is True
    assert result["similarity"] >= 0.70

def test_true_negative_pair(engine):
    data = load_fixture("true_negative_pair.json")
    result = engine.analyze_pair(data["posts_a"], data["posts_b"])

    assert result["is_eligible"] is True
    assert result["similarity"] < 0.60

def test_short_corpus_gate(engine):
    data = load_fixture("short_corpus.json")
    result = engine.analyze_pair(data["posts_a"], data["posts_b"])

    assert result["is_eligible"] is False
    assert "below 5 posts" in result["reason"] or "below 1500" in result["reason"]

def test_mixed_language_gate(engine):
    data = load_fixture("mixed_language.json")
    result = engine.analyze_pair(data["posts_a"], data["posts_b"])

    assert result["is_eligible"] is False
    assert "Non-English language" in result["reason"]

def test_llm_imitation(engine):
    data = load_fixture("llm_imitation.json")
    result = engine.analyze_pair(data["posts_a"], data["posts_b"])

    assert result["is_eligible"] is True
    # Similarity should be recorded
    assert "similarity" in result

def test_template_heavy_cleaning(engine):
    data = load_fixture("template_heavy.json")
    # Cleaned corpus should not contain PGP key blocks or market TOS
    cleaned = engine.clean_corpus(data["posts_a"])
    assert "BEGIN PGP PUBLIC KEY BLOCK" not in cleaned
    assert "FE only for buyers" not in cleaned
    assert "Actual post content" in cleaned

def test_adversarial_cleaning(engine):
    data = load_fixture("adversarial.json")
    cleaned = engine.clean_corpus(data["posts_a"])
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" not in cleaned
    assert "0x0000000000000000000000000000000000000000" not in cleaned
    assert "http://example.onion" not in cleaned
    assert "BEGIN PGP SIGNATURE" not in cleaned
    assert "Hello everyone. I am releasing a new software tool" in cleaned
