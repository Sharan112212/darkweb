from collection.fixture_replayer import FixtureReplayer

def test_fixture_replayer_success(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")

    assert capture.status == "succeeded"
    assert b"GhostVendor" in content
    assert capture.http_status == 200

def test_fixture_replayer_offline_503(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)
    capture, content = replayer.fetch_fixture("fixture://market-a/ghostvendor_offline.html")

    assert capture.status == "failed"
    assert capture.http_status == 503
    assert b"503 Service Temporarily Unavailable" in content
