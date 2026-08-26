# 🔬 Dark Web Threat Actor De-anonymization System — Project Reference

**Document Purpose:** Complete human reference for understanding, setting up, implementing, and demoing this project.
**Last Updated:** 2026-08-26
**PS ID:** 26151 | **Theme:** Blockchain & Cybersecurity | **Org:** NTRO

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Project Architecture](#2-project-architecture)
3. [Complete Component Inventory](#3-complete-component-inventory)
4. [The Three De-anonymization Vectors](#4-the-three-de-anonymization-vectors)
5. [Sample Data Overview](#5-sample-data-overview)
6. [Tech Stack](#6-tech-stack)
7. [Prerequisites Checklist](#7-prerequisites-checklist)
8. [Step-by-Step Lab Setup](#8-step-by-step-lab-setup)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Database Schema](#10-database-schema)
11. [Dashboard Design](#11-dashboard-design)
12. [Demo Script](#12-demo-script)
13. [Key Design Decisions](#13-key-design-decisions)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What This Project Is

A **self-contained, self-hosted mock dark web laboratory** that provides a safe, realistic environment for:
- Scraping synthetic dark web marketplace data via the **real Tor network**
- Correlating threat actor identities across three independent signal types
- Surfacing attribution results in a searchable, exportable dashboard

**Nothing touches real dark web infrastructure.** Everything is synthetic: fake personas, fake posts, fake "vulnerable" infrastructure — all owned and controlled end-to-end.

### The Narrative (for your video)
> "We built a self-contained lab simulating dark web infrastructure and marketplace activity, with deliberately planted misconfigurations and synthetic actor personas — including a rebrand case with shared identifiers and a harder rebrand case with none. Our scraper collects this data live over the real Tor network, and our analysis pipeline runs on that collected data, not hardcoded values."

---

## 2. Project Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Mock Tor Lab (Docker Compose)                      │
│                                                                      │
│  ┌──────────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ nginx-hidden (:80/443)│  │ marketplace:5000│  │ nginx-clearnet  │  │
│  │ Planted misconfigs +  │  │ Flask App with  │  │ :8443 (HTTPS)   │  │
│  │ Shared SSL Cert       │  │ Synthetic Data  │  │ Shared SSL Cert │  │
│  └──────────┬────────────┘  └───────┬─────────┘  └───────┬─────────┘ │
│             │                       │                     │           │
│  ┌──────────────────────────────────────────────────┐     │           │
│  │         tor-daemon (SOCKS5 @ Port 9050)           │     │           │
│  │   Publishes 2 .onion hidden services              │     │           │
│  └──────────┬───────────────────────┬────────────────┘     │           │
└─────────────┼───────────────────────┼──────────────────────┼───────────┘
              │                       │                      │
              ▼                       ▼                      ▼
  ┌────────────────────┐  ┌────────────────────┐  ┌─────────────────────┐
  │ Infra-Matcher       │  │ Scraper            │  │ (Direct HTTPS)      │
  │ (cert fingerprint)  │  │ (Tor SOCKS proxy)  │  │                     │
  └─────────┬───────────┘  └─────────┬──────────┘  └──────────┬──────────┘
            │                        │                         │
            │                        ▼                         │
            │              ┌──────────────────┐                │
            │              │  SQLite DB        │                │
            │              │  darkweb_intel.db │                │
            │              │  (actors, posts)  │                │
            │              └────────┬─────────┘                │
            │                       │                          │
            │         ┌─────────────┼─────────────┐            │
            │         ▼             ▼             ▼            │
            │  ┌────────────┐ ┌──────────┐ ┌────────────┐      │
            │  │ Identity   │ │Stylometry│ │ Infra      │◀─────┘
            │  │ Graph      │ │ Module   │ │ Matcher    │
            │  │(PGP/Wallet)│ │ (SBERT)  │ │(cert match)│
            │  └─────┬──────┘ └────┬─────┘ └─────┬──────┘
            │        │             │              │
            │        ▼             ▼              ▼
            │  ┌───────────────────────────────────────────┐
            └─▶│  relationship_links + infra_links tables  │
               └───────────────────┬───────────────────────┘
                                   ▼
               ┌───────────────────────────────────────────┐
               │         Streamlit Dashboard               │
               │  Search / Filter / Profile / Export        │
               └───────────────────────────────────────────┘
```

---

## 3. Complete Component Inventory

### Already Built ✅

| Component | Location | Description |
|---|---|---|
| **docker-compose.yml** | `./docker-compose.yml` | Orchestrates 4 services on `lab-net` bridge network |
| **Tor daemon** | `./tor/` | Debian container running Tor, publishes 2 hidden services, SOCKS5 on :9050 |
| **nginx-hidden** | `./nginx-hidden/` | "SecureVault Hosting" — dark web site with 3 planted misconfigs |
| **nginx-clearnet** | `./nginx-clearnet/` | "TechCorp Cloud Solutions" — clearnet twin sharing same SSL cert |
| **Cert generator** | `./certs/generate_certs.sh` | Creates `shared_cert.pem` + `shared_key.pem` for both nginx instances |
| **Marketplace** | `./marketplace/` | Flask app serving 8 personas + 18 posts from JSON, accessible as .onion |
| **Sample data** | `./sample_data/` | `personas.json` (8 actors) + `posts.json` (18 posts) |
| **Scraper** | `./scraper/` | Tor-aware crawler → writes to SQLite `darkweb_intel.db` |
| **Infra matcher** | `./infra-matcher/` | Compares SSL cert SHA-256 fingerprints between hidden + clearnet |
| **Documentation** | `./docs/` | PRD, TRD, App_Flow, Backend_Schema, Implementation_Plan |

### To Be Built 🔧

| Module | File | What It Does |
|---|---|---|
| **DB Schema Extension** | `db_setup.py` | Creates `relationship_links`, `infra_links`, `actor_infra_map` tables + indexes |
| **Identity Graph** | `identity_graph.py` | Groups actors by shared PGP/wallet → writes to `relationship_links` |
| **Stylometry** | `stylometry.py` | Sentence-BERT embeddings + cosine similarity → writes to `relationship_links` |
| **Infra Matcher (DB write)** | `match_infra.py` (modify) | Adds DB persistence alongside console output |
| **Pipeline Runner** | `run_pipeline.py` | Single-command execution of all analysis modules |
| **Dashboard** | `dashboard.py` | Streamlit UI: search, profiles, linked personas, export |
| **Graph Viz (P1)** | In `dashboard.py` | pyvis network graph on actor profile page |
| **JSON/PDF Export (P1)** | In `dashboard.py` | Additional export formats |

---

## 4. The Three De-anonymization Vectors

### Vector 1: Infrastructure Misconfiguration Correlation (G1/FR4)
- **Signal:** Shared SSL/TLS certificate between hidden service and clearnet site
- **Module:** `infra-matcher/match_infra.py`
- **How:** Fetches DER X.509 cert from both endpoints, computes SHA-256, compares
- **Demo case:** nginx-hidden (SecureVault Hosting) shares cert with nginx-clearnet (TechCorp Cloud Solutions)
- **Planted misconfigs in nginx-hidden:**
  1. Open `/server-status` endpoint (information disclosure)
  2. `X-Powered-By: nginx/1.25.3 (Ubuntu)` header (banner leakage)
  3. Reused SSL certificate (the critical deanonymization vector)

### Vector 2: Cross-Marketplace Identity Graph (G2/FR2)
- **Signal:** Shared PGP fingerprint or cryptocurrency wallet address
- **Module:** `identity_graph.py` (to be built)
- **How:** Groups actors by exact match on non-null `pgp_fingerprint` or `wallet_address`
- **Demo case:** `DarkFox` ↔ `DarkFox_v2` — same PGP key + same BTC wallet = easy rebrand

### Vector 3: AI-Driven Stylometric Persona Linking (G3/FR3)
- **Signal:** Writing style similarity (no shared identifiers)
- **Module:** `stylometry.py` (to be built)
- **How:** Sentence-BERT (`all-MiniLM-L6-v2`) embeddings + cosine similarity
- **Demo case:** `GhostVendor` ↔ `Nightshade99` — completely different PGP/wallet but:
  - Same slang ("yo fam", "ngl", "stay safe out there fam")
  - Same misspelling ("definately")
  - Same sign-off pattern
  - Same phrasing about "quality checked twice" and "patience pays off"

---

## 5. Sample Data Overview

### 8 Personas (`personas.json`)

| Handle | Category | Source | Purpose |
|---|---|---|---|
| **DarkFox** | stolen_data | SecureVault Market | Easy rebrand — original identity |
| **DarkFox_v2** | stolen_data | SecureVault Market | Easy rebrand — shares PGP + wallet with DarkFox |
| **GhostVendor** | arms | Obsidian Forum | Hard rebrand — old identity (inactive) |
| **Nightshade99** | arms | Obsidian Forum | Hard rebrand — new identity (different PGP/wallet, same writing style) |
| cipherqueen | hacking_services | SecureVault Market | Background/control persona |
| moneymule_88 | money_laundering | Obsidian Forum | Background/control persona |
| pillcartel_x | drugs | SecureVault Market | Background/control persona |
| redroom_admin | fraud | Obsidian Forum | Background/control persona |

### 18 Posts (`posts.json`)

| Handle | # Posts | Writing Style |
|---|---|---|
| GhostVendor | 3 | Informal: "yo fam", "ngl", "definately", "stay safe out there fam" |
| Nightshade99 | 3 | **Same style as GhostVendor** — key stylometry signal |
| DarkFox | 2 | Formal/professional: "Please be advised", "Professionalism is expected" |
| DarkFox_v2 | 2 | **Same style as DarkFox** — also linked by identifiers |
| cipherqueen | 2 | Technical, terse |
| moneymule_88 | 2 | Very short, blunt |
| pillcartel_x | 2 | Enthusiastic, uses "!!" |
| redroom_admin | 2 | Authoritative, rule-focused |

---

## 6. Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Containerization | Docker + Docker Compose | Isolated mock lab with 4 services |
| Tor Network | Real Tor daemon | Authentic .onion hidden service publishing |
| Web Server | nginx:alpine | Hidden service + clearnet twin |
| Marketplace App | Flask 3.0.3 (Python) | Serves synthetic data via HTTP |
| Scraper | requests[socks] + BeautifulSoup | Tor-aware crawling via SOCKS5h proxy |
| Infra Matching | Python ssl/socket + PySocks | SSL cert fingerprint comparison |
| Database | SQLite (darkweb_intel.db) | Zero setup, sufficient at prototype scale |
| Identity Graph | Plain Python (SQL grouping) | Exact match on PGP/wallet, no ML needed |
| Stylometry | sentence-transformers (all-MiniLM-L6-v2) | CPU-capable, good accuracy/speed tradeoff |
| Graph (in-memory) | NetworkX | No separate graph DB needed at this scale |
| Dashboard | Streamlit | Fastest path to demo-ready UI |
| Export | pandas (CSV/JSON), reportlab (PDF) | Standard, low-effort |
| Visualization (P1) | pyvis | Interactive network graphs in browser |

---

## 7. Prerequisites Checklist

Use this as a tick-list before starting implementation:

- [ ] **Docker Desktop** installed and running
- [ ] **Docker Compose v2+** available (`docker compose version`)
- [ ] **Python 3.10+** installed (`python --version`)
- [ ] **OpenSSL** available (`openssl version`) — on Windows, use Git Bash
- [ ] **Git Bash** installed (Windows only, for running `.sh` scripts)
- [ ] **pip** available (`pip --version`)
- [ ] SSL certificates generated (`certs/shared_cert.pem` + `certs/shared_key.pem` exist)
- [ ] Docker lab running (`docker compose up --build -d` → 4 containers green)
- [ ] Both .onion addresses obtained and saved
- [ ] Scraper run successfully (8 actors, ~18 posts in `darkweb_intel.db`)
- [ ] Infra matcher shows `[MATCH]`
- [ ] Python packages installed: `streamlit sentence-transformers pandas networkx pyvis reportlab requests[socks] beautifulsoup4`

---

## 8. Step-by-Step Lab Setup

```
Step 1:  Generate certs           →  ./certs/generate_certs.sh
Step 2:  Start Docker lab         →  docker compose up --build -d
Step 3:  Wait 30-60s for Tor      →  (Tor publishes hidden services)
Step 4:  Get onion addresses      →  docker exec tor-daemon cat /var/lib/tor/hidden_service_*/hostname
Step 5:  (Optional) Manual verify →  Visit marketplace .onion in Tor Browser
Step 6:  Run scraper              →  python scraper.py --onion <marketplace>.onion
Step 7:  Run infra-matcher        →  python match_infra.py --onion <vulnerable>.onion
Step 8:  Run pipeline             →  python run_pipeline.py  (after modules are built)
Step 9:  Launch dashboard         →  streamlit run dashboard.py
```

---

## 9. Implementation Roadmap

| Step | Module | Priority | Depends On | Creates/Modifies |
|---|---|---|---|---|
| 1 | DB Schema Extension | P0 | Scraper data | `db_setup.py` [NEW] |
| 2 | Identity Graph | P0 | Step 1 | `identity_graph.py` [NEW] |
| 3 | Stylometry | P0 | Step 1 | `stylometry.py` [NEW] |
| 4 | Infra Matcher DB Write | P0 | Step 1 | `match_infra.py` [MODIFY] |
| 5 | Pipeline Runner | P0 | Steps 1-3 | `run_pipeline.py` [NEW] |
| 6 | Dashboard | P0 | Steps 1-5 | `dashboard.py` [NEW] |
| 7 | Graph Visualization | P1 | Step 6 | `dashboard.py` [ENHANCE] |
| 8 | JSON/PDF Export | P1 | Step 6 | `dashboard.py` [ENHANCE] |

---

## 10. Database Schema

### Existing Tables (from scraper)

```sql
actors (handle PK, category, source, status, last_seen, pgp_fingerprint, wallet_address)
posts  (id PK AUTO, handle FK, timestamp, text)
```

### New Tables (from db_setup.py)

```sql
relationship_links (
  id INTEGER PK AUTO,
  actor_a TEXT NOT NULL FK→actors,
  actor_b TEXT NOT NULL FK→actors,
  link_type TEXT NOT NULL CHECK IN ('shared_identifier', 'stylometric'),
  evidence TEXT NOT NULL,
  confidence_score INTEGER NOT NULL CHECK 0-100,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (actor_a, actor_b, link_type)
)

infra_links (
  id INTEGER PK AUTO,
  onion_address TEXT NOT NULL,
  clearnet_host TEXT NOT NULL,
  evidence TEXT NOT NULL,
  confidence_score INTEGER NOT NULL CHECK 0-100,
  matched_at TEXT DEFAULT CURRENT_TIMESTAMP
)

actor_infra_map (handle FK→actors, onion_address FK→infra_links)
```

### Key Indexes
```sql
idx_posts_handle ON posts(handle)
idx_links_actor_a ON relationship_links(actor_a)
idx_links_actor_b ON relationship_links(actor_b)
```

---

## 11. Dashboard Design

### Screen 1 — Search / Home
- Search bar: handle, category, or identifier
- Category dropdown: drugs / arms / hacking_services / fraud / money_laundering / stolen_data
- Date range picker on `last_seen`
- Results table: handle, category, source, last_seen, # linked actors

### Screen 2 — Actor Profile
- Header: handle, category, source, status, last_seen
- Identifiers: PGP fingerprint, wallet address
- Linked Personas (grouped by link_type with confidence & evidence)
- Infrastructure matches (if any)
- Raw posts
- Export button

### Screen 3 — Bulk Export
- Multi-select from results table
- Export as CSV (P0) / JSON / PDF (P1)

### Edge Cases
- No results → "No matching actors found"
- No links → "No links found"
- Zero selection export → button disabled

---

## 12. Demo Script (90 seconds, for video recording)

1. **Open dashboard** → show all actors on home screen
2. **Search "DarkFox"** → open profile → show link to `DarkFox_v2` (95% confidence, shared PGP key)
3. **Search "Nightshade99"** → open profile → show link to `GhostVendor` (stylometric, lower confidence) → **explicitly say:** "This pair shares no PGP key or wallet — this link was found through AI stylometric analysis only"
4. **Show infra match** → vulnerable hidden service traced to clearnet twin (TechCorp Cloud Solutions)
5. **Filter + Export** → filter by category, select rows, export CSV, show downloaded file

---

## 13. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Single `relationship_links` table** for both identity graph and stylometry outputs | Dashboard has one simple query surface regardless of which module produced the link |
| **SQLite, not Postgres** | Zero setup, sufficient at prototype scale (8 actors, 18 posts) |
| **NetworkX in-memory, not Neo4j** | No extra Docker service needed at this scale |
| **`all-MiniLM-L6-v2` model** | Runs on CPU, no GPU needed, good accuracy/speed tradeoff |
| **Streamlit, not FastAPI+React** | Fastest path to demo-ready UI for a small team |
| **`INSERT OR IGNORE` everywhere** | All modules are idempotent — safe to re-run without duplicates |
| **Evidence required on every link** | Explainability: no bare scores, analyst can always see *why* |
| **Configurable thresholds** | Similarity threshold, DB path, proxy address as top-of-file constants for easy tuning |

---

## 14. Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `.onion` hostname files don't exist | Tor hasn't finished publishing yet | Wait 60 seconds, retry |
| Scraper hangs/timeouts | Tor circuit not established | Restart `tor-daemon` container, wait, retry |
| `[NO MATCH]` from infra-matcher | Certs not generated or not mounted | Re-run `generate_certs.sh`, then `docker compose up --build` |
| Stylometry doesn't rank GhostVendor/Nightshade99 highest | Threshold too high or posts too short | Lower threshold from 0.75, check posts.json has enough text |
| `ModuleNotFoundError: sentence_transformers` | Package not installed | `pip install sentence-transformers` |
| Streamlit won't start | Port conflict | `streamlit run dashboard.py --server.port 8502` |
| Docker containers won't start | Docker Desktop not running | Start Docker Desktop first |
| sqlite3 command not found (Windows) | Not in PATH | Use Python's `sqlite3` module or install via Git Bash |

---

*This document is maintained alongside the project. Update it as components are built and verified.*
