# 🔬 Dark Web Threat Actor De-anonymization System — Project Reference

**Document Purpose:** Complete human reference for understanding, setting up, implementing, and demoing this project.
**Last Updated:** 2026-08-27
**PS ID:** 26151 | **Theme:** Blockchain & Cybersecurity | **Org:** NTRO

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Project Architecture](#2-project-architecture)
3. [Complete Component Inventory](#3-complete-component-inventory)
4. [De-anonymization Vectors & Multi-Signal Fusion](#4-de-anonymization-vectors--multi-signal-fusion)
5. [Analyst Feedback Loop](#5-analyst-feedback-loop)
6. [Sample Data Overview](#6-sample-data-overview)
7. [Tech Stack](#7-tech-stack)
8. [Prerequisites Checklist](#8-prerequisites-checklist)
9. [Step-by-Step Lab Setup](#9-step-by-step-lab-setup)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Database Schema](#11-database-schema)
12. [Dashboard Design](#12-dashboard-design)
13. [Demo Script](#13-demo-script)
14. [Key Design Decisions](#14-key-design-decisions)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What This Project Is

A **self-contained, self-hosted mock dark web laboratory** that provides a safe, realistic environment for:
- Scraping synthetic dark web marketplace data via the **real Tor network**
- Correlating threat actor identities across three independent signal types
- Fusing independent weak/medium signals into high-confidence lead scores via Noisy-OR probabilistic fusion
- Collecting analyst confirmation feedback to measure historical signal reliability
- Surfacing attribution results in a searchable, exportable Streamlit dashboard

**Nothing touches real dark web infrastructure.** Everything is synthetic: fake personas, fake posts, fake "vulnerable" infrastructure — all owned and controlled end-to-end.

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
            │        ▼             ▼              │
            │  ┌──────────────────────────────┐   │
            │  │    relationship_links        │   │
            │  └──────────────┬───────────────┘   │
            │                 │                   │
            │                 ▼                   │
            │  ┌──────────────────────────────┐   │
            │  │ Multi-Signal Fusion Engine   │   │
            │  │ (Noisy-OR Probabilistic Math)│   │
            │  └──────────────┬───────────────┘   │
            │                 │                   │
            │                 ▼                   ▼
            │  ┌───────────────────────────────────────────┐
            └─▶│  fused_links, infra_links, link_feedback  │
               └───────────────────┬───────────────────────┘
                                   ▼
               ┌───────────────────────────────────────────┐
               │   Streamlit Dashboard + Analyst Feedback  │
               │  Search / Filter / Profile / 👍 Feedback  │
               └───────────────────────────────────────────┘
```

---

## 3. Complete Component Inventory

| Component | Location | Description |
|---|---|---|
| **docker-compose.yml** | `./docker-compose.yml` | Orchestrates 4 services on `lab-net` bridge network |
| **Tor daemon** | `./tor/` | Debian container running Tor, publishes 2 hidden services, SOCKS5 on :9050 |
| **nginx-hidden** | `./nginx-hidden/` | Dark web site with 3 planted misconfigurations |
| **nginx-clearnet** | `./nginx-clearnet/` | Clearnet twin sharing identical SSL certificate |
| **Cert generator** | `./certs/generate_certs.sh` | Generates `shared_cert.pem` + `shared_key.pem` |
| **Marketplace** | `./marketplace/` | Flask app serving 10 personas + 22 posts from JSON |
| **Sample data** | `./sample_data/` | `personas.json` (10 actors) + `posts.json` (22 posts) |
| **Scraper** | `./scraper/` | Tor-aware crawler → writes to SQLite `darkweb_intel.db` & `actor_infra_map` |
| **DB Setup** | `./db_setup.py` | Schema extension script (adds relationship_links, fused_links, link_feedback, actor_infra_map) |
| **Identity Graph** | `./identity_graph.py` | Links actors by PGP fingerprint (95%) and wallet address (90%) |
| **Model Pre-cacher** | `./download_model.py` | Pre-caches SBERT model weights locally to `./models/all-MiniLM-L6-v2` for offline inference |
| **Stylometry** | `./stylometry.py` | Sentence-BERT embeddings + cosine similarity writing style matcher (loads locally from `./models/`) |
| **Fusion Engine** | `./fusion.py` | Noisy-OR probabilistic multi-signal fusion engine (with normalized `min(A,B), max(A,B)` pair ordering) |
| **Feedback Stats** | `./feedback_stats.py` | Computes historical signal reliability percentages from analyst feedback |
| **Infra matcher** | `./infra-matcher/` | Compares SSL cert SHA-256 fingerprints, populates `infra_links` & `actor_infra_map` |
| **Pipeline Runner** | `./run_pipeline.py` | Executable orchestrating db_setup → identity_graph → stylometry → fusion |
| **Dashboard** | `./dashboard.py` | Streamlit UI with multi-signal fusion badge, analyst feedback buttons, and export |

---

## 4. De-anonymization Vectors & Multi-Signal Fusion

### Signal 1: Infrastructure Misconfiguration Correlation
- **Module:** `infra-matcher/match_infra.py`
- **Method:** SSL/TLS certificate SHA-256 fingerprint comparison between `.onion` endpoint and clearnet twin.

### Signal 2: Cross-Marketplace Identity Graph
- **Module:** `identity_graph.py`
- **Method:** Exact match grouping on non-null `pgp_fingerprint` (95% confidence) and `wallet_address` (90% confidence).

### Signal 3: AI-Driven Stylometric Persona Linking
- **Module:** `stylometry.py`
- **Method:** Sentence-BERT (`all-MiniLM-L6-v2`) embeddings + pairwise cosine similarity on post text.

### Probabilistic Multi-Signal Fusion (`fusion.py`)
Commercial tools output separate disjoint leads. Our fusion engine combines independent signals using the **Noisy-OR model**:

$$\text{fused\_confidence} = \text{round}\left( \left(1 - \prod_{i=1}^{n} (1 - c_i / 100)\right) \times 100 \right)$$

#### Live Demonstration Example:
- `ViperX` ↔ `ViperX_Reborn`:
  - Signal A (Shared BTC Wallet): **90%**
  - Signal B (Stylometry Writing Match): **84%**
  - **Multi-Signal Fused Score:** $1 - (0.10 \times 0.16) = \mathbf{98\%}$ 🔥 (Boosted across 2 independent signals!)

---

## 5. Analyst Feedback Loop

The system includes a human-in-the-loop feedback mechanism (`link_feedback` table):
- **Interactive UI Buttons:** Analysts click `👍 Confirm` or `👎 False Positive` on attribution cards in Streamlit.
- **Reliability Metric Computation (`feedback_stats.py`):**
  $$\text{Reliability \%} = \frac{\text{Confirmed Feedback}}{\text{Total Feedback}} \times 100$$
- **Sidebar Integration:** Real-time signal reliability percentages display in the dashboard sidebar, giving analysts empirical confidence context.

---

## 6. Sample Data Overview

### 10 Personas (`personas.json`)

| Handle | Category | Source | Purpose |
|---|---|---|---|
| **DarkFox** | stolen_data | SecureVault Market | Easy rebrand — original identity |
| **DarkFox_v2** | stolen_data | SecureVault Market | Easy rebrand — shares PGP + wallet with DarkFox |
| **GhostVendor** | arms | Obsidian Forum | Hard rebrand — old identity (inactive) |
| **Nightshade99** | arms | Obsidian Forum | Hard rebrand — new identity (same writing style) |
| **ViperX** | hacking_services | SecureVault Market | Multi-signal fusion case — original identity |
| **ViperX_Reborn** | hacking_services | Obsidian Forum | Multi-signal fusion case — shares wallet AND writing style (fused score: 98%) |
| cipherqueen | hacking_services | SecureVault Market | Background/control persona |
| moneymule_88 | money_laundering | Obsidian Forum | Background/control persona |
| pillcartel_x | drugs | SecureVault Market | Background/control persona |
| redroom_admin | fraud | Obsidian Forum | Background/control persona |

---

## 7. Database Schema

```sql
actors (handle PK, category, source, status, last_seen, pgp_fingerprint, wallet_address)
posts (id PK AUTO, handle FK, timestamp, text)

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

fused_links (
  id INTEGER PK AUTO,
  actor_a TEXT NOT NULL FK→actors,
  actor_b TEXT NOT NULL FK→actors,
  fused_confidence INTEGER NOT NULL CHECK 0-100,
  contributing_link_types TEXT NOT NULL,
  signal_count INTEGER NOT NULL,
  evidence_summary TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (actor_a, actor_b)
)

link_feedback (
  id INTEGER PK AUTO,
  link_id INTEGER,
  link_source TEXT NOT NULL,
  feedback TEXT NOT NULL CHECK IN ('confirmed', 'rejected'),
  analyst_note TEXT,
  submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
)

infra_links (
  id INTEGER PK AUTO,
  onion_address TEXT NOT NULL,
  clearnet_host TEXT NOT NULL,
  evidence TEXT NOT NULL,
  confidence_score INTEGER NOT NULL CHECK 0-100,
  matched_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

---

## 8. Step-by-Step Lab Setup & Execution

```bash
# 1. Generate SSL certificates
./certs/generate_certs.sh

# 2. Launch Docker environment
docker compose up --build -d

# 3. Pre-cache SBERT model locally for offline inference
python download_model.py

# 4. Initialize Database Schema (creates all tables & constraints)
python db_setup.py

# 5. Get onion addresses & run scraper
docker exec tor-daemon cat /var/lib/tor/hidden_service_marketplace/hostname
python scraper/scraper.py --onion <marketplace>.onion

# 6. Run full attribution pipeline (schema -> identity -> stylometry -> fusion)
py run_pipeline.py

# 7. Run infrastructure matcher
py infra-matcher/match_infra.py --onion <vulnerable>.onion

# 8. Launch Streamlit Dashboard
py -m streamlit run dashboard.py
```

---

*This document is maintained alongside the project. Updated 2026-08-27 with Multi-Signal Fusion and Analyst Feedback Loop documentation.*
