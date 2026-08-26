# Product Requirements Document (PRD)
## Dark Web Threat Actor De-anonymization System — Prototype Build

**PS ID:** 26151 | **Org:** NTRO | **Theme:** Blockchain & Cybersecurity
**Version:** 2.0 (post-lab-scaffold, ready for implementation)

---

## 1. Purpose

A system that ingests dark web actor footprints (from our self-hosted mock lab for demo purposes), correlates them across three independent signal types — infrastructure leaks, shared identifiers, and writing style — and surfaces the resulting attribution in a searchable, exportable dashboard.

## 2. Users

**Primary:** Cyber threat intelligence analyst.
**Core need:** given a handle or identifier, quickly see everything it's linked to, how confident that link is, and why.

## 3. Goals (in priority order for prototype)

| # | Goal | Priority |
|---|---|---|
| G1 | Ingest scraped actor/post data into a structured database | P0 |
| G2 | Auto-link actors sharing PGP key / wallet address (identity graph) | P0 |
| G3 | Score writing-style similarity between actors with no shared identifiers (stylometry) | P0 |
| G4 | Correlate hidden service infra to clearnet infra via cert fingerprint | P0 |
| G5 | Searchable dashboard: query by handle/category/date, view linked profile | P0 |
| G6 | Export results as CSV | P0 |
| G7 | Export results as JSON / PDF report | P1 |
| G8 | Timeline/date-range filtering | P1 |
| G9 | Graph visualization in-dashboard (not just a table) | P1 |

## 4. Non-goals

- No live scraping of real dark web sources (demo runs on our own mock lab)
- No active exploitation of any infrastructure not owned by the team
- No production-grade auth/access control (prototype is single-user, local)
- No claim of definitive real-world identity — outputs are investigative leads with confidence scores, never certainties

## 5. Functional Requirements

Each maps to a module already scaffolded in `darkweb-lab/`:

- **FR1 (Data ingestion):** `scraper/scraper.py` writes into `darkweb_intel.db`. No changes needed unless schema evolves — see Backend Schema doc.
- **FR2 (Identity graph):** New module. Reads `actors` table, groups by matching `pgp_fingerprint` or `wallet_address`, outputs linked clusters + evidence.
- **FR3 (Stylometry):** New module. Reads `posts` table, computes pairwise similarity per actor (embedding-based), outputs top matches + evidence, excluding pairs already linked by FR2.
- **FR4 (Infra matching):** `infra-matcher/match_infra.py` already does this for the demo case; wrap its output into the DB so the dashboard can display it alongside the other two link types.
- **FR5 (Confidence scoring):** A unified score (0-100) per relationship link, computed differently per link type but stored in one common table (see Backend Schema) so the dashboard doesn't need to know the source module.
- **FR6 (Dashboard):** Search, actor profile view (identifiers + all link types + confidence + evidence), category/date filters.
- **FR7 (Export):** CSV always; JSON/PDF if time allows.

## 6. Success Criteria (demo-ready definition of done)

- Running the scraper → identity graph → stylometry → infra matcher → dashboard, in that order, with zero manual data entry, produces:
  - `DarkFox` / `DarkFox_v2` linked via shared identifier, confidence ~95-100%
  - `GhostVendor` / `Nightshade99` linked via stylometry only, confidence clearly above unrelated pairs
  - The vulnerable hidden service linked to its clearnet twin via cert match
- Dashboard search for any of the above returns a profile showing all applicable links with evidence
- CSV export of a filtered result set opens correctly in Excel/Sheets
