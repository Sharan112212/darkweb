"""
Database schema extension for the PS 26151 prototype.

Adds the analysis tables (relationship_links, infra_links, actor_infra_map)
and indexes to the existing darkweb_intel.db created by the scraper.

Run this once after the scraper has populated actors/posts and before
running the identity-graph / stylometry / infra-matcher modules.

USAGE:
    python db_setup.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")


def setup_schema():
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at {DB_PATH}")
        print("    Run the scraper first to create the database.")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        -- Common sink for identity-graph and stylometry links
        CREATE TABLE IF NOT EXISTS relationship_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_a TEXT NOT NULL,
            actor_b TEXT NOT NULL,
            link_type TEXT NOT NULL CHECK (link_type IN ('shared_identifier', 'stylometric')),
            evidence TEXT NOT NULL,
            confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (actor_a) REFERENCES actors(handle),
            FOREIGN KEY (actor_b) REFERENCES actors(handle),
            UNIQUE (actor_a, actor_b, link_type)
        );

        -- Infra fingerprint matches
        CREATE TABLE IF NOT EXISTS infra_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            onion_address TEXT NOT NULL,
            clearnet_host TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
            matched_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Optional: link an actor to an infra match
        CREATE TABLE IF NOT EXISTS actor_infra_map (
            handle TEXT,
            onion_address TEXT,
            FOREIGN KEY (handle) REFERENCES actors(handle),
            FOREIGN KEY (onion_address) REFERENCES infra_links(onion_address)
        );

        -- Multi-signal fusion confidence scores
        CREATE TABLE IF NOT EXISTS fused_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_a TEXT NOT NULL,
            actor_b TEXT NOT NULL,
            fused_confidence INTEGER NOT NULL CHECK (fused_confidence BETWEEN 0 AND 100),
            contributing_link_types TEXT NOT NULL,
            signal_count INTEGER NOT NULL,
            evidence_summary TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (actor_a) REFERENCES actors(handle),
            FOREIGN KEY (actor_b) REFERENCES actors(handle),
            UNIQUE (actor_a, actor_b)
        );

        -- Analyst feedback loop
        CREATE TABLE IF NOT EXISTS link_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            link_source TEXT NOT NULL,
            feedback TEXT NOT NULL CHECK (feedback IN ('confirmed', 'rejected')),
            analyst_note TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes for query performance
        CREATE INDEX IF NOT EXISTS idx_posts_handle ON posts(handle);
        CREATE INDEX IF NOT EXISTS idx_links_actor_a ON relationship_links(actor_a);
        CREATE INDEX IF NOT EXISTS idx_links_actor_b ON relationship_links(actor_b);
        CREATE INDEX IF NOT EXISTS idx_fused_actors ON fused_links(actor_a, actor_b);
    """)

    conn.commit()

    # Print summary
    cur.execute("SELECT COUNT(*) FROM actors")
    actors_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM posts")
    posts_count = cur.fetchone()[0]

    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    conn.close()

    print("[+] Schema extended successfully.")
    print(f"    Tables: {', '.join(tables)}")
    print(f"    Existing data: {actors_count} actors, {posts_count} posts")
    return True


if __name__ == "__main__":
    setup_schema()
