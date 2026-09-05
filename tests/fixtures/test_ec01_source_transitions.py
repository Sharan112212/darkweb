from collection.fixture_replayer import FixtureReplayer

def test_ec01_source_offline_transition(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)

    # 1. Capture online fixture
    cap1, content1 = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert cap1.status == "succeeded"

    # 2. Source goes offline (503) -> Status event created, old evidence retained
    cap2, content2 = replayer.fetch_fixture("fixture://market-a/ghostvendor_offline.html")
    assert cap2.status == "failed"
    assert cap2.http_status == 503

    # 3. Source returns online with changed content -> New capture record created
    cap3, content3 = replayer.fetch_fixture("fixture://market-a/ghostvendor_changed.html")
    assert cap3.status == "succeeded"
    assert cap3.sha256 != cap1.sha256
