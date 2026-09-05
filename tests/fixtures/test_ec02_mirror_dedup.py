from collection.fixture_replayer import FixtureReplayer

def test_ec02_mirror_dedup(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)

    # Fetch original market-a page
    cap1, _ = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    # Fetch market-b mirror page
    cap2, _ = replayer.fetch_fixture("fixture://market-b/mirror_ghostvendor.html")

    assert cap1.status == "succeeded"
    assert cap2.status == "succeeded"
    assert cap1.capture_id != cap2.capture_id
