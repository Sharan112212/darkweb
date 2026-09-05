"""
Offline seed loader for the PS 26151 prototype.

Loads the synthetic fixtures in ``sample_data/`` (personas.json, posts.json)
directly into ``scraper/darkweb_intel.db`` so the analysis pipeline
(identity_graph -> stylometry -> fusion -> dashboard) can be demonstrated
WITHOUT standing up the Docker + Tor + scraper stack.

This mirrors what the Tor scraper would produce after crawling the mock
marketplace, but works fully air-gapped (relevant for EC-37).

USAGE:
    python seed_data.py          # ensures schema, then seeds actors + posts
"""
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "scraper", "darkweb_intel.db")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")


def _load_json(name):
    path = os.path.join(SAMPLE_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_database(force=False):
    """Load sample_data JSON into the database.

    Ensures the schema exists first (via db_setup), then loads personas into
    ``actors`` and posts into ``posts``. Idempotent: actors use
    INSERT OR REPLACE keyed on the handle PK, and posts for each seeded handle
    are cleared before re-insertion so re-running never duplicates rows.

    Args:
        force: kept for API symmetry; seeding is always idempotent.

    Returns:
        (actors_loaded, posts_loaded) tuple.
    """
    # Ensure the schema exists before we write to it.
    from db_setup import setup_schema
    setup_schema()

    personas = _load_json("personas.json")
    posts = _load_json("posts.json")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- Actors ---
    for p in personas:
        cur.execute(
            """
            INSERT OR REPLACE INTO actors
            (handle, category, source, status, last_seen, pgp_fingerprint, wallet_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p.get("handle"),
                p.get("category"),
                p.get("source"),
                p.get("status"),
                p.get("last_seen"),
                p.get("pgp_fingerprint"),
                p.get("wallet_address"),
            ),
        )
    actors_loaded = len(personas)

    # --- Posts (idempotent: clear the handles we are about to seed) ---
    seeded_handles = {p["handle"] for p in posts if p.get("handle")}
    for handle in seeded_handles:
        cur.execute("DELETE FROM posts WHERE handle = ?", (handle,))

    posts_loaded = 0
    for post in posts:
        handle = post.get("handle")
        if not handle:
            continue
        cur.execute(
            "INSERT INTO posts (handle, timestamp, text) VALUES (?, ?, ?)",
            (handle, post.get("timestamp", ""), post.get("text", "")),
        )
        posts_loaded += 1

    conn.commit()
    conn.close()

    print(f"[+] Seeded {actors_loaded} actors and {posts_loaded} posts into {DB_PATH}")
    return actors_loaded, posts_loaded


def actors_table_is_empty():
    """Return True if the database has no actor rows (or no DB/table yet)."""
    if not os.path.exists(DB_PATH):
        return True
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM actors")
        count = cur.fetchone()[0]
    except sqlite3.OperationalError:
        count = 0
    finally:
        conn.close()
    return count == 0


if __name__ == "__main__":
    seed_database()
