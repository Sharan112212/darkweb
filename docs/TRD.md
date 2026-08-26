# Technical Requirements Document (TRD)
## Dark Web Threat Actor De-anonymization System — Prototype

---

## 1. System Architecture

```
┌──────────────┐   ┌───────────────┐   ┌──────────────────┐
│ Mock Tor Lab │──▶│  Scraper      │──▶│  SQLite DB        │
│ (docker-     │   │ (scraper.py)  │   │  darkweb_intel.db │
│  compose)    │   └───────────────┘   └─────────┬─────────┘
└──────────────┘                                  │
        │                                          │
        ▼                                          ▼
┌──────────────┐                      ┌────────────────────────┐
│ Infra-Matcher│─────writes to───────▶│  relationship_links     │
│ (cert check) │                      │  table                  │
└──────────────┘                      └────────────┬────────────┘
                                                     │
        ┌──────────────────┐   ┌─────────────────┐  │
        │ Identity Graph    │──▶│                 │◀─┘
        │ (PGP/wallet match)│   │  relationship_  │
        └──────────────────┘   │  links table     │
        ┌──────────────────┐   │  (shared sink)   │
        │ Stylometry Module │──▶│                 │
        │ (embedding sim.)  │   └────────┬────────┘
        └──────────────────┘             │
                                          ▼
                              ┌────────────────────────┐
                              │  Dashboard (Streamlit)  │
                              │  search / filter / view │
                              │  / export               │
                              └────────────────────────┘
```

**Key design decision:** all three analysis modules (identity graph, stylometry,
infra-matcher) write into one common `relationship_links` table with a
`link_type` field, so the dashboard has a single, simple query surface
regardless of which module produced the link. This is the piece that keeps
the system coherent — don't let each module invent its own output format.

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Database | SQLite (`darkweb_intel.db`) | Already in use by scraper; zero setup, fine at prototype scale |
| Graph representation | NetworkX (in-memory, generated on demand from `relationship_links`) | No separate graph DB needed at this scale; avoids extra Docker service |
| Stylometry | `sentence-transformers` (`all-MiniLM-L6-v2`) + cosine similarity | Good accuracy/speed tradeoff, runs on CPU, no GPU needed |
| Dashboard | Streamlit | Fastest path to a working, demo-ready UI for a small team |
| Export | `pandas` (CSV/JSON), `reportlab` (PDF, P1) | Standard, low-effort |
| Scraping | `requests[socks]` + `BeautifulSoup` (already built) | No change needed |
| Infra matching | Python `ssl`/`socket` + PySocks (already built) | No change needed |

## 3. Module Interfaces

### 3.1 Identity Graph Module (`identity_graph.py`)
- **Input:** reads `actors` table from `darkweb_intel.db`
- **Logic:** group rows where `pgp_fingerprint` matches (non-null) OR `wallet_address` matches (non-null)
- **Output:** inserts rows into `relationship_links`:
  `(actor_a, actor_b, link_type='shared_identifier', evidence, confidence_score)`
  - `evidence` = e.g. `"shared PGP fingerprint"` or `"shared wallet address"`
  - `confidence_score` = 95 for exact PGP match, 90 for exact wallet match (both are effectively certain — hardcode these, no ML needed)

### 3.2 Stylometry Module (`stylometry.py`)
- **Input:** reads `posts` table, grouped by `handle`
- **Logic:** concatenate each actor's posts → embed with SBERT → compute pairwise cosine similarity across all actor pairs NOT already linked in `relationship_links`
- **Output:** for pairs above a threshold (start at 0.75, tune after testing), insert into `relationship_links`:
  `(actor_a, actor_b, link_type='stylometric', evidence, confidence_score)`
  - `evidence` = top shared phrases/style markers (can be a simple text summary, doesn't need to be exhaustive)
  - `confidence_score` = similarity score scaled to 0-100

### 3.3 Infra Matcher (`match_infra.py`, extend existing)
- **Input:** cert fingerprints from hidden service + clearnet endpoint (already implemented)
- **Output:** on match, insert into a new `infra_links` table (see schema doc):
  `(onion_address, clearnet_host, evidence='SSL certificate fingerprint match', confidence_score=98)`

### 3.4 Dashboard (`dashboard.py`)
- **Reads:** `actors`, `posts`, `relationship_links`, `infra_links`
- **Provides:**
  - Search box (handle/category)
  - Actor profile page: identifiers, all linked actors (grouped by link_type), confidence scores, evidence text, any matched infra
  - Date range filter on `last_seen`
  - Export button → CSV (and JSON/PDF if built)

## 4. Non-Functional Requirements

- **Explainability:** every row in `relationship_links` must have non-null `evidence` — no bare scores.
- **Idempotency:** re-running any module should not create duplicate links (use `INSERT OR IGNORE` or a uniqueness constraint on `(actor_a, actor_b, link_type)`).
- **Performance:** at prototype scale (dozens of actors, hundreds of posts), all modules should run in well under a minute — no need to optimize beyond straightforward pandas/SQL.
- **Config:** similarity threshold, DB path, and Tor proxy address should be constants at the top of each script, not hardcoded deep in logic — makes tuning easy during demo prep.

## 5. Testing Checklist (before recording)

- [ ] Scraper populates both `actors` and `posts` with all 8 personas
- [ ] Identity graph correctly links `DarkFox` ↔ `DarkFox_v2` and nothing else spuriously
- [ ] Stylometry correctly ranks `GhostVendor` ↔ `Nightshade99` as top (or clearly top-3) pair
- [ ] Infra matcher returns `[MATCH]` for the vulnerable service
- [ ] Dashboard search for `DarkFox` shows the link to `DarkFox_v2` with evidence
- [ ] Dashboard search for `Nightshade99` shows the stylometric link to `GhostVendor` with evidence
- [ ] CSV export opens cleanly and contains the expected columns
