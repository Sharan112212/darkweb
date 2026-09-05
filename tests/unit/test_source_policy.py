from collection.capture_manager import CaptureManager

def test_source_allowlist_check(temp_db):
    cm = CaptureManager(temp_db)
    assert cm.is_source_allowlisted("fixture://market-a/ghostvendor.html") is True
    assert cm.is_source_allowlisted("fixture://blocked/captcha_page.html") is False

def test_kill_switch(temp_db):
    cm = CaptureManager(temp_db)
    cm.policy["kill_switch"] = True
    assert cm.is_source_allowlisted("fixture://market-a/ghostvendor.html") is False
