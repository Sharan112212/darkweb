# Implementation Plan
## Dark Web Threat Actor De-anonymization System — Prototype

This plan sequences the build so each step produces something testable
before moving to the next, and gives you ready-to-paste prompts for
Antigravity at each step.

---

## Pre-step: verify the lab (you do this, not the agent)

Before writing any new code, confirm the existing `darkweb-lab/` scaffold
actually runs:
1. `./certs/generate_certs.sh`
2. `docker compose up --build -d`
3. Grab both onion addresses
4. Run `scraper/scraper.py` → confirm `darkweb_intel.db` has 8 rows in `actors`, ~18 in `posts`
5. Run `infra-matcher/match_infra.py` → confirm `[MATCH]`

**Do not proceed until this works.** Every later step depends on real data existing in the DB.

---

## Step 1 — Extend the schema

**Goal:** add `relationship_links` and `infra_links` tables.

**Antigravity prompt:**
> "In the darkweb-lab project, create `db_setup.py` at the project root that connects to `scraper/darkweb_intel.db` and creates two new tables: `relationship_links` (actor_a, actor_b, link_type, evidence, confidence_score, created_at, unique on actor_a+actor_b+link_type) and `infra_links` (onion_address, clearnet_host, evidence, confidence_score, matched_at). Use `CREATE TABLE IF NOT EXISTS`. Full schema is in docs/Backend_Schema.md — follow it exactly."

**Verify:** run it, then `sqlite3 scraper/darkweb_intel.db ".tables"` shows all 4 tables.

---

## Step 2 — Identity graph module

**Goal:** auto-link actors sharing PGP key or wallet.

**Antigravity prompt:**
> "Create `identity_graph.py` at the project root. Read the `actors` table from `scraper/darkweb_intel.db`. Group actors by identical non-null `pgp_fingerprint`, and separately by identical non-null `wallet_address`. For each group with more than one actor, insert a row into `relationship_links` for every pair, with link_type='shared_identifier', evidence describing which field matched (e.g. 'shared PGP fingerprint'), and confidence_score=95 for PGP matches or 90 for wallet matches. Use INSERT OR IGNORE to avoid duplicate errors on re-run. Print a summary of links created."

**Verify:** `DarkFox` and `DarkFox_v2` show up as a linked pair with confidence 95.

---

## Step 3 — Stylometry module

**Goal:** catch the hard-rebrand case with no shared identifiers.

**Antigravity prompt:**
> "Create `stylometry.py` at the project root. Install sentence-transformers. Read all posts from `scraper/darkweb_intel.db`, group text by handle (concatenate each actor's posts into one string). Compute sentence embeddings using the 'all-MiniLM-L6-v2' model for each actor's combined text. Compute cosine similarity between every pair of actors that do NOT already have a row in relationship_links. For pairs scoring above 0.75, insert into relationship_links with link_type='stylometric', evidence='writing style similarity: {score}', confidence_score = similarity*100 rounded to nearest int. Print the top 5 highest-scoring pairs regardless of threshold so I can tune it."

**Verify:** `GhostVendor`/`Nightshade99` appears clearly at or near the top of the printed ranking. If it's not clearly separated from noise, lower the threshold and/or ask Antigravity to try TF-IDF stylistic features (avg word length, punctuation frequency, function-word ratios) as a fallback/complement — sometimes more reliable than embeddings on very short text samples.

---

## Step 4 — Wire infra-matcher into the DB

**Goal:** get the infra match result into the same database the dashboard reads from.

**Antigravity prompt:**
> "Modify infra-matcher/match_infra.py so that when a certificate match is found, it also writes a row into the infra_links table in scraper/darkweb_intel.db (onion_address, clearnet_host, evidence='SSL certificate fingerprint match', confidence_score=98), instead of only printing to console."

**Verify:** after running it, `infra_links` has one row.

---

## Step 5 — One-command pipeline runner (for demo reliability)

**Antigravity prompt:**
> "Create run_pipeline.py at the project root that runs, in order: db_setup.py, identity_graph.py, stylometry.py, and prints a final summary of how many rows are in actors, posts, relationship_links, and infra_links. Do not include the scraper or infra-matcher in this script since those need onion addresses as arguments — just note in a comment that those must be run manually first."

**Verify:** one command rebuilds all derived tables from scratch.

---

## Step 6 — Dashboard

**Goal:** the screen you'll actually record.

**Antigravity prompt:**
> "Create dashboard.py using Streamlit, reading from scraper/darkweb_intel.db. Follow the flow in docs/App_Flow.md exactly: a home screen with search bar, category dropdown filter, and date range filter over a results table of actors; clicking a row (or a details expander) shows an actor profile with identifiers, a 'Linked Personas' section grouped by link_type (query relationship_links where actor_a or actor_b matches), an infrastructure match section if one exists in infra_links, and the actor's raw posts. Include a CSV export button for the current filtered table using pandas. Handle empty search results and actors with no links gracefully per the edge cases in docs/App_Flow.md."

**Verify:** run `streamlit run dashboard.py`, walk through the exact demo script in `docs/App_Flow.md` section 3, confirm every step works.

---

## Step 7 — P1 additions (only if time remains)

In order of value for the time cost:
1. Graph visualization (pyvis) embedded in the actor profile page — biggest visual upgrade
2. JSON export alongside CSV
3. PDF report export (reportlab)

**Antigravity prompt (graph viz):**
> "Add a graph visualization to dashboard.py using pyvis: on an actor's profile page, render a network graph showing that actor and all directly linked actors as nodes, with edges labeled by link_type and confidence_score. Embed it in the Streamlit page using streamlit.components.v1.html."

---

## Step 8 — Integration test (you do this, not the agent)

Run the full sequence once, start to finish, on the machine you'll record on:
`docker compose up` → get onion addresses → `scraper.py` → `run_pipeline.py` → `match_infra.py` → `streamlit run dashboard.py` → walk the demo script.

Fix anything broken. Do this with enough buffer before your deadline to
survive at least one bad surprise.

---

## Step 9 — Record

Follow the video structure and script notes from the earlier planning
doc (problem framing → live walkthrough of the App_Flow demo script →
roadmap/production-scope closing note).

---

## Prompting notes for Antigravity throughout

- Always point it at `docs/Backend_Schema.md`, `docs/TRD.md`, or `docs/App_Flow.md` in the prompt rather than re-explaining the schema/flow from memory each time — keeps it consistent across sessions.
- One module per session/prompt. Don't ask for Steps 2+3+6 in one go.
- After each step, actually run the code yourself and check the output against the "Verify" line above before moving to the next step — don't chain three unverified AI-generated modules together.
