from collection.tor_collector import TorCollector

def test_tor_collector_proxy_setting():
    tc = TorCollector(socks_proxy="socks5h://127.0.0.1:9050")
    assert tc.socks_proxy == "socks5h://127.0.0.1:9050"

def test_tor_collector_blocked_source(temp_db):
    tc = TorCollector(db_path=temp_db)
    capture, content = tc.fetch("fixture://blocked/captcha_page.html")
    assert capture.status == "blocked"
    assert capture.not_collected_reason == "Source blocked by policy"
