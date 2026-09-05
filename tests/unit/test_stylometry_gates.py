from analysis.classical_stylometry import ClassicalStylometryEngine

def test_post_count_gate_failure():
    engine = ClassicalStylometryEngine()
    posts = ["Post 1", "Post 2", "Post 3", "Post 4"]
    eligible, reason, _ = engine.check_eligibility(posts)
    assert eligible is False
    assert "below 5 posts" in reason

def test_char_count_gate_failure():
    engine = ClassicalStylometryEngine()
    posts = ["Short post text."] * 5
    eligible, reason, meta = engine.check_eligibility(posts)
    assert eligible is False
    assert "below 1500" in reason
    assert meta["post_count"] == 5

def test_non_english_gate_failure():
    engine = ClassicalStylometryEngine()
    russian_text = "Это просто тестовое сообщение на русском языке без английских слов. " * 30
    posts = [russian_text] * 5
    eligible, reason, _ = engine.check_eligibility(posts)
    assert eligible is False
    assert "Non-English" in reason or "below 1500" in reason or "No valid words" in reason

def test_cleaning_pipeline_removes_pgp_and_wallets():
    engine = ClassicalStylometryEngine()
    raw = [
        "-----BEGIN PGP PUBLIC KEY BLOCK-----\nmQENBF...\n-----END PGP PUBLIC KEY BLOCK-----",
        "Send funds to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or 0x1234567890123456789012345678901234567890",
        "> Quoting someone else: this is quoted text.",
        "https://example.onion/market/item/123",
        "Valid text content that should remain after cleaning."
    ]
    cleaned = engine.clean_corpus(raw)
    assert "BEGIN PGP" not in cleaned
    assert "1A1zP1eP" not in cleaned
    assert "0x12345678" not in cleaned
    assert "Quoting someone else" not in cleaned
    assert "https://example.onion" not in cleaned
    assert "Valid text content" in cleaned
