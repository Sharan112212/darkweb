# Backend Schema
## Dark Web Threat Actor De-anonymization System — Prototype

Database: SQLite, file `darkweb_intel.db` (already created by `scraper.py`,
extended here with the tables the analysis modules need).

---

## 1. Existing tables (from scraper.py — do not change without updating the scraper)

```sql
CREATE TABLE actors (
    handle TEXT PRIMARY KEY,
    category TEXT,
    source TEXT,
    status TEXT,
    last_seen TEXT,
    pgp_fingerprint TEXT,
    wallet_address TEXT
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handle TEXT,
    timestamp TEXT,
    text TEXT,
    FOREIGN KEY (handle) REFERENCES actors(handle)
);
```

## 2. New tables (add these — one script, run once before the analysis modules)

```sql
-- Common sink for identity-graph and stylometry links
CREATE TABLE relationship_links (
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
CREATE TABLE infra_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onion_address TEXT NOT NULL,
    clearnet_host TEXT NOT NULL,
    evidence TEXT NOT NULL,
    confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    matched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Optional: link an actor to an infra match, if a scraped source can be
-- tied to a specific onion address (useful if you scale past 2 mock services)
CREATE TABLE actor_infra_map (
    handle TEXT,
    onion_address TEXT,
    FOREIGN KEY (handle) REFERENCES actors(handle),
    FOREIGN KEY (onion_address) REFERENCES infra_links(onion_address)
);
```

## 3. Indexes (add once data volume grows past trivial — fine to skip at prototype scale, but here for completeness)

```sql
CREATE INDEX idx_posts_handle ON posts(handle);
CREATE INDEX idx_links_actor_a ON relationship_links(actor_a);
CREATE INDEX idx_links_actor_b ON relationship_links(actor_b);
```

## 4. Setup script

Create `db_setup.py` in the project root:

```python
import sqlite3

conn = sqlite3.connect("scraper/darkweb_intel.db")
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS relationship_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_a TEXT NOT NULL,
    actor_b TEXT NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN ('shared_identifier', 'stylometric')),
    evidence TEXT NOT NULL,
    confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (actor_a, actor_b, link_type)
);

CREATE TABLE IF NOT EXISTS infra_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onion_address TEXT NOT NULL,
    clearnet_host TEXT NOT NULL,
    evidence TEXT NOT NULL,
    confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    matched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_posts_handle ON posts(handle);
CREATE INDEX IF NOT EXISTS idx_links_actor_a ON relationship_links(actor_a);
CREATE INDEX IF NOT EXISTS idx_links_actor_b ON relationship_links(actor_b);
""")

conn.commit()
conn.close()
print("Schema extended successfully.")
```

Run this once, after the scraper has populated `actors`/`posts` and before
running the identity-graph / stylometry / infra-matcher modules.

## 5. Query examples the dashboard will use

**Get an actor's profile with all links:**
```sql
SELECT * FROM actors WHERE handle = ?;

SELECT actor_a, actor_b, link_type, evidence, confidence_score
FROM relationship_links
WHERE actor_a = ? OR actor_b = ?;
```

**Filter by category and date range:**
```sql
SELECT * FROM actors
WHERE category = ?
AND last_seen BETWEEN ? AND ?;
```

**Get infra match for a source, if any:**
```sql
SELECT * FROM infra_links WHERE onion_address = ?;
```
