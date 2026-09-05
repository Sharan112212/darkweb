from collection.normalizer import CollectionNormalizer

def test_normalizer_safe_html():
    norm = CollectionNormalizer()
    raw = b"<html><head><script>alert('xss');</script></head><body><h1>Safe Title</h1></body></html>"
    safe_text, meta = norm.normalize(raw)

    assert meta["status"] == "valid"
    assert "<script>" not in safe_text
    assert "Safe Title" in safe_text

def test_normalizer_oversized_quarantine():
    norm = CollectionNormalizer()
    oversized_raw = b"A" * (10 * 1024 * 1024 + 100) # Exceeds 10MB
    safe_text, meta = norm.normalize(oversized_raw)

    assert meta["status"] == "quarantined"
    assert "exceeds 10MB limit" in meta["reason"]
