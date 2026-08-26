"""
Tor-aware scraper for the PS 26151 prototype.

Crawls the mock marketplace hidden service (run via docker-compose) over
the real Tor network, parses persona/post pages, and writes results into
a local SQLite database matching the PRD schema.

USAGE:
  1. `docker compose up` in the project root (this starts nginx-hidden,
     nginx-clearnet, marketplace, and tor).
  2. Find your .onion address:
       docker exec -it tor-daemon cat /var/lib/tor/hidden_service_marketplace/hostname
  3. Run this script:
       python scraper.py --onion <your-onion-address>.onion
"""
import argparse
import re
import sqlite3
import requests
from bs4 import BeautifulSoup

TOR_PROXY = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

DB_PATH = "darkweb_intel.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actors (
            handle TEXT PRIMARY KEY,
            category TEXT,
            source TEXT,
            status TEXT,
            last_seen TEXT,
            pgp_fingerprint TEXT,
            wallet_address TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            handle TEXT,
            timestamp TEXT,
            text TEXT
        )
    """)
    conn.commit()
    return conn


def scrape(onion_address):
    base = f"http://{onion_address}"
    conn = init_db()
    cur = conn.cursor()

    print(f"[*] Connecting to {base} via Tor...")
    index_resp = requests.get(base + "/", proxies=TOR_PROXY, timeout=60)
    soup = BeautifulSoup(index_resp.text, "html.parser")

    handles = [a.text.strip() for a in soup.select("a")]
    print(f"[*] Found {len(handles)} actor handles on index page")

    for handle in handles:
        profile_url = f"{base}/user/{handle}"
        try:
            resp = requests.get(profile_url, proxies=TOR_PROXY, timeout=60)
        except Exception as e:
            print(f"[!] Failed to fetch {handle}: {e}")
            continue

        psoup = BeautifulSoup(resp.text, "html.parser")
        text = psoup.get_text("\n")

        category = _extract(text, r"Category:\s*(.+)")
        source = _extract(text, r"Source:\s*(.+)")
        status = _extract(text, r"Status:\s*(.+)")
        last_seen = _extract(text, r"Last seen:\s*(.+)")
        pgp = _extract(text, r"PGP fingerprint:\s*(.+)")
        wallet = _extract(text, r"Wallet:\s*(.+)")

        cur.execute("""
            INSERT OR REPLACE INTO actors
            (handle, category, source, status, last_seen, pgp_fingerprint, wallet_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (handle, category, source, status, last_seen, pgp, wallet))

        for li in psoup.select("ul li"):
            post_text = li.get_text(" ", strip=True)
            if post_text and "PGP" not in post_text:
                cur.execute(
                    "INSERT INTO posts (handle, timestamp, text) VALUES (?, ?, ?)",
                    (handle, "", post_text)
                )

        print(f"[+] Scraped {handle}")

    conn.commit()
    conn.close()
    print(f"[*] Done. Data written to {DB_PATH}")


def _extract(text, pattern):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--onion", required=True, help="marketplace .onion address")
    args = parser.parse_args()
    scrape(args.onion)
