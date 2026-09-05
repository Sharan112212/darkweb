# Baseline Audit — SIH26151

**Branch:** feat/branch-0-baseline-audit
**Auditor:** Dev B (scoring & interface lane)
**Date:** 2026-09-05
**Method:** direct source reading. Every claim below cites a file and line. No runtime code was changed; findings are documented, not fixed.

---

## Repository layout as found

**Step 0 output.** All expected modules exist at the **repository root** — there is no `darklabdoc/darkweb-lab/` nesting anywhere in the tree. The planning docs that mention that path are describing an intended layout that does not match this repo. The repo root *is* the project.

Python files found:

```
./dashboard.py
./db_setup.py
./download_model.py
./feedback_stats.py
./fusion.py
./identity_graph.py
./infra-matcher/match_infra.py     ← Dev A
./marketplace/app.py               ← mock market (not in audit scope)
./run_pipeline.py                  ← Dev A
./scraper/scraper.py               ← Dev A
./stylometry.py
```

Expected-path confirmation table:

| Expected path | Actual path | Status |
|---|---|---|
| `identity_graph.py` | `identity_graph.py` (root) | CONFIRMED |
| `stylometry.py` | `stylometry.py` (root) | CONFIRMED |
| `fusion.py` | `fusion.py` (root) | CONFIRMED |
| `dashboard.py` | `dashboard.py` (root) | CONFIRMED |
| `feedback_stats.py` | `feedback_stats.py` (root) | CONFIRMED |
| `db_setup.py` | `db_setup.py` (root) | CONFIRMED |
| `sample_data/` | `sample_data/` (root) — `personas.json`, `posts.json` | CONFIRMED |

Notable findings from orientation:

- **No `tests/` directory exists anywhere in the repo.** Test coverage for every module below is therefore **zero**. This is stated once here and referenced per module rather than repeated.
- The database file is `scraper/darkweb_intel.db` — every Dev B module hardcodes `DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")`. The DB lives *inside* the scraper directory, not at root.
- The SBERT model is pre-cached under `models/all-MiniLM-L6-v2/` by `download_model.py`.
- `db_setup.py` creates **7 user tables** (see B0.5) — the plan's count of 7 is correct. (SQLite additionally auto-creates `sqlite_sequence` for the `AUTOINCREMENT` tables, so `sqlite_master` reports 8 rows.) The stale doc is `docs/Backend_Schema.md`, which documents only 5 tables — it omits `fused_links` and `link_feedback` entirely.

---

## Module: identity_graph

| Field | Finding |
|---|---|
| File path | `identity_graph.py` |
| Entry point | `run_identity_graph()` — no args, returns `links_created` (int). CLI via `if __name__ == "__main__"` (`identity_graph.py:87`). |
| Language / runtime | Python 3, stdlib only (`sqlite3`, `os`, `itertools.combinations`). |
| Input format | Reads `actors` table from `scraper/darkweb_intel.db`. Two `GROUP BY` queries (see below). |
| Output format | Writes to `relationship_links` with fixed `link_type='shared_identifier'` (`identity_graph.py:46`, `:72`). |
| Dependencies | `sqlite3`, `os`, `itertools` — no third-party, no ML (`identity_graph.py:11-13`). |
| Current test data | `sample_data/personas.json` (DarkFox/DarkFox_v2 share PGP+wallet; ViperX/ViperX_Reborn share wallet only). |
| Test coverage | **None.** No `tests/` directory exists. |

### What it actually does

Two independent passes, each identical in shape:

**PGP pass** (`identity_graph.py:29-52`):
```sql
SELECT pgp_fingerprint, GROUP_CONCAT(handle, '||')
FROM actors
WHERE pgp_fingerprint IS NOT NULL AND pgp_fingerprint != ''
GROUP BY pgp_fingerprint
HAVING COUNT(*) > 1
```
For each group it splits the concatenated handles on `||` and forms all pairs with `combinations(handles, 2)` (`identity_graph.py:40`). Pair ordering is normalised with `min/max` (`identity_graph.py:41`). Insert is `INSERT OR IGNORE` (`identity_graph.py:44`).

**Wallet pass** (`identity_graph.py:55-78`): the same, grouping on `wallet_address`.

### Confidence values — every literal

- `PGP_CONFIDENCE = 95` — `identity_graph.py:18`
- `WALLET_CONFIDENCE = 90` — `identity_graph.py:19`

**Both are hardcoded module-level constants.** They are not computed, not read from config, not adjusted by evidence quality. The comment at `identity_graph.py:17` states the rationale: *"Confidence scores for exact matches (no ML needed — these are deterministic)."* Every PGP link is written at exactly 95; every wallet link at exactly 90 (`identity_graph.py:47`, `:73`).

### Indicator handling (PGP)

- Fingerprints are compared **as raw strings** via SQL `GROUP BY pgp_fingerprint` — no normalisation, no case-folding, no whitespace stripping (`identity_graph.py:33`). In `sample_data/personas.json` the fingerprints are stored with embedded spaces and a double-space mid-string (e.g. `"9A3F 21B4 77C0 EE12 5D6A  8F90 ..."`, `personas.json:6`). Two actors match only if their fingerprint strings are **byte-identical**, spacing included.
- **EC-10 (published key vs verified signature): CONFIRMED ABSENT.** There is no distinction whatsoever between a PGP key that was merely *published* on a profile and one whose *signature was cryptographically verified*. The module only knows the `pgp_fingerprint` column value; possession/verification is never modelled. A shared published key is scored identically (95) to a verified one.

### Wallet handling

- **EC-09 (wallet roles): CONFIRMED ABSENT.** No distinction between personal, shared-service, escrow, or mixer wallets. Any two actors sharing a `wallet_address` string are linked at 90 regardless of what that address represents. A shared deposit address at a common exchange or mixer would produce a false 90% link — the module cannot tell.
- Chain/network is **not distinguished.** The sample data mixes BTC bech32 (`bc1q...`), BTC legacy P2PKH (`1...`) and P2SH (`3...`) addresses in the same `wallet_address` column (`personas.json:7,38,49`). The matcher is a pure string equality, so cross-chain collision is impossible here but also means no chain metadata is ever recorded or used.

### Alias normalisation (EC-11)

**CONFIRMED ABSENT.** There is no alias concept and no normalisation of the `handle` value. Handles flow through `GROUP_CONCAT`, `.split("||")`, and `min/max` ordering (`identity_graph.py:41`) as raw strings. Comparison is case-sensitive ASCII ordering; no case-folding, no Unicode NFC/NFKC, no whitespace trimming. `DarkFox` and `darkfox` would be treated as different actors.

### Pair generation mechanism

`itertools.combinations(handles, 2)` over handles produced by SQL `GROUP_CONCAT(handle, '||')` then `.split("||")` (`identity_graph.py:30`, `:39-40`). Not a self-join; the grouping is done in SQL and the pairing in Python.

### Provenance on output

**None.** The `relationship_links` row carries only `actor_a, actor_b, link_type, evidence, confidence_score, created_at`. `evidence` is a free-text string like `f"Shared PGP fingerprint: {fingerprint}"` (`identity_graph.py:47`). There is **no capture ID, no source URL, no timestamp of observation, no evidence hash**. `created_at` records when the row was written, not when the indicator was observed.

### Security concerns

- Hardcoded 95/90 confidence gives every shared-identifier link a misleadingly precise, uniform score with no uncertainty — an analyst sees "95%" for a shared *published* key that may prove nothing (`identity_graph.py:18`, EC-10).
- No wallet-role gating means a mixer/exchange address links unrelated actors at 90% (`identity_graph.py:19`, EC-09).

### Data-provenance gaps

- No observation timestamp, source URL, or capture ID on any link (`identity_graph.py:43-47`). An analyst cannot trace *where* the shared fingerprint was seen.
- No evidence hash — the claim is not tamper-evident.

### Adapter required

An `identity_evidence_adapter` that wraps `run_identity_graph`'s output and adds: `indicator_type` (`pgp_fingerprint` / `wallet_address`), an `indicator_role` field to close EC-10 (`key_published` vs `verified_signature`) and EC-09 (wallet role), a provenance block (capture ID, source URL, observed-at timestamp, content hash), and PGP-fingerprint normalisation (strip whitespace, upper-case) to close EC-11 before comparison.

---

## Module: stylometry

| Field | Finding |
|---|---|
| File path | `stylometry.py` |
| Entry point | `run_stylometry()` — no args, returns `links_created` (int). CLI at `stylometry.py:142`. |
| Language / runtime | Python 3 + `sentence-transformers` (imported lazily inside the function, `stylometry.py:32-37`). |
| Input format | `SELECT handle, text FROM posts ORDER BY handle` (`stylometry.py:43`). |
| Output format | Writes `relationship_links` with `link_type='stylometric'` (`stylometry.py:127`). |
| Dependencies | `sqlite3`, `os`, `warnings`, `itertools`; `sentence_transformers.SentenceTransformer`, `util` (`stylometry.py:33`). |
| Current test data | `sample_data/posts.json` — GhostVendor↔Nightshade99 (hard rebrand, style-only), ViperX↔ViperX_Reborn. |
| Test coverage | **None.** |

### What it actually does

1. Loads all posts, groups text per handle, concatenates each actor's posts into one blob joined by spaces (`stylometry.py:52-63`).
2. Loads SBERT — from `models/all-MiniLM-L6-v2/` if it exists, else downloads by name (`stylometry.py:73-79`).
3. `model.encode(texts, convert_to_tensor=True)` — one embedding per actor (`stylometry.py:82`).
4. All pairwise `util.cos_sim` over `combinations(range(len(handles)), 2)` (`stylometry.py:93-96`).
5. Writes every pair with `sim >= SIMILARITY_THRESHOLD` (`stylometry.py:113-133`).

### Model loading — pinned or runtime? (EC-37)

- Model is `MODEL_NAME = "all-MiniLM-L6-v2"` (`stylometry.py:27`) — **pinned by name only, not by hash or version.**
- Air-gap capable *if* `models/all-MiniLM-L6-v2/` is pre-populated by `download_model.py`: the code prefers the local dir (`stylometry.py:74-76`). But the fallback path (`stylometry.py:78-79`) fetches from the network at runtime, so an air-gapped run with an empty `models/` dir fails. There is no integrity check on the cached weights (no hash pin) — EC-37 is only partially satisfied.

### Similarity threshold — literal or configurable?

`SIMILARITY_THRESHOLD = 0.75` — `stylometry.py:24`. A hardcoded module-level literal. The comment cites the TRD and says *"tune after seeing results"* (`stylometry.py:23`). Not read from config or CLI. The written confidence is `int(round(sim * 100))` (`stylometry.py:120`) — i.e. the confidence *is* the cosine score rescaled, with no calibration.

### The `link_type` string — does it overstate? (SUBSTANTIVE FINDING)

The literal written to the DB is **`'stylometric'`** (`stylometry.py:127`). The evidence string is `f"Writing style similarity score: {sim:.4f} (Sentence-BERT cosine similarity)"` (`stylometry.py:121`). The dashboard renders this under the heading **"🧠 Linked via Writing Style (AI Stylometry)"** (`dashboard.py:369`).

**This label overstates what the measurement demonstrates.** What is actually computed is the cosine similarity between two *sentence-embedding* vectors produced by `all-MiniLM-L6-v2` — a **semantic** similarity model. It measures *what the posts are about*, not *how the author writes*. Two different vendors both posting terse "fresh stock, quality checked, DM me" ads will score high on semantic similarity while sharing no authorial fingerprint. Classical stylometry (function-word frequencies, character n-grams, punctuation/idiolect features) is **not implemented anywhere**. Calling this "stylometry" / "writing style" attributes authorship-level evidentiary weight to what is really topic/register similarity. This should be relabelled `semantic_similarity` in the enum, with `classical_stylometry` reserved for a real stylometric signal that does not yet exist. Migration note recorded in `docs/indicator-types.md`.

### Corpus gates (min post count / char count / language)

**CONFIRMED ABSENT.** The only gate is truthiness: `if text and text.strip()` per post (`stylometry.py:54`) and `if combined:` per actor (`stylometry.py:62`). An actor with a single 5-word post is embedded and compared exactly like one with 50 posts. No minimum post count, no minimum character count. This is exactly the EC that lets a two-word actor generate a spurious high-similarity link.

### Text cleaning before embedding (EC-21)

**CONFIRMED ABSENT.** Text is used verbatim — only `.strip()` and space-join (`stylometry.py:57`, `:61`). Templates, quoted text, PGP blocks, and signatures are **not** stripped. In this corpus the posts are already prose, but boilerplate ("stay safe out there fam", "Professionalism is expected from all buyers") is repeated across a single actor's own posts and drives self-similarity; shared boilerplate across actors would inflate cross-actor scores.

### Language detection (EC-19)

**CONFIRMED ABSENT.** No language detection at any point. All posts are embedded regardless of language; cross-language similarity is neither checked nor flagged.

### Where post text comes from / dedup

`posts.text` via `SELECT handle, text FROM posts ORDER BY handle` (`stylometry.py:43`). **No deduplication** of posts — if the scraper inserts the same post twice, it is counted twice in the concatenation, biasing that actor's embedding. Dedup exists only at the *link* level (`stylometry.py:84-88` reads existing `'stylometric'` pairs to skip), not the post level.

### Security concerns

- Runtime model download on cache miss (`stylometry.py:78-79`) violates air-gap assumptions and is a supply-chain surface — no hash pin (EC-37).
- The `'stylometric'` label + "AI Stylometry" UI heading overstate the evidence, risking analyst over-trust of a semantic-similarity score presented as authorship (`stylometry.py:127`, `dashboard.py:369`).

### Data-provenance gaps

- Same as identity graph: no capture ID, source URL, observation timestamp, or evidence hash on the written link (`stylometry.py:124-128`).
- The similarity score is not reproducible without recording the model version/hash — none is stored.

### Adapter required

A `stylometry_evidence_adapter` that: relabels output as `semantic_similarity` (not stylometric); records the model name + weights hash for reproducibility (EC-37); enforces corpus gates — minimum post count and character count before a pair is emitted; strips boilerplate/templates/PGP/signatures (EC-21); adds language detection and gates or flags cross-language pairs (EC-19); and attaches the provenance block.

---

## Module: fusion

| Field | Finding |
|---|---|
| File path | `fusion.py` |
| Entry point | `run_fusion()` — no args, returns count of fused pairs. CLI at `fusion.py:111`. |
| Language / runtime | Python 3, stdlib only (`sqlite3`, `os`, `math`; `math` is imported but never used, `fusion.py:15`). |
| Input format | `SELECT actor_a, actor_b, link_type, evidence, confidence_score FROM relationship_links` (`fusion.py:36-39`). |
| Output format | `INSERT OR REPLACE INTO fused_links (actor_a, actor_b, fused_confidence, contributing_link_types, signal_count, evidence_summary)` (`fusion.py:87-91`). |
| Dependencies | stdlib only. Reads only `relationship_links`; does **not** read `infra_links` (see deviation). |
| Current test data | ViperX↔ViperX_Reborn (wallet + stylometric = two signals), DarkFox↔DarkFox_v2 (PGP + wallet, both 'shared_identifier'). |
| Test coverage | **None.** |

### The actual algorithm, step by step

1. Fetch every `relationship_links` row (`fusion.py:36-40`).
2. Group rows by normalised pair `(min(a,b), max(a,b))` into `pair_links[pair] = [ {link_type, evidence, confidence}, ... ]` (`fusion.py:48-57`).
3. For each pair:
   - `confidences = [l['confidence'] for l in links]` — **all** links in the pair, not deduplicated (`fusion.py:63`).
   - `link_types = list(dict.fromkeys(...))` — **deduplicated**, order-preserving (`fusion.py:64`).
   - Noisy-OR (`fusion.py:66-72`):
     ```
     prob_not_linked = 1.0
     for c in confidences:
         prob_not_linked *= (1.0 - c/100.0)
     fused_prob = 1.0 - prob_not_linked
     fused_confidence = int(round(fused_prob * 100.0))
     ```
   - Cap: `if fused_confidence > 99 and max(confidences) < 100: fused_confidence = 99` (`fusion.py:74-76`).
   - `signal_count = len(link_types)` — the **deduplicated** count (`fusion.py:79`).
4. `INSERT OR REPLACE` one row per pair (`fusion.py:87-91`).

### Is it noisy-OR? — CONFIRMED

Yes. `1 - Π(1 - cᵢ)` is implemented literally at `fusion.py:66-72`, matching the module docstring (`fusion.py:5-6`).

### Where do weights come from?

**From the `confidence_score` already stored in `relationship_links`.** There is no weight table, no config, no per-signal weighting inside fusion. The inputs are whatever identity_graph (hardcoded 95/90) and stylometry (rescaled cosine) wrote. Fusion applies no reweighting — every input confidence enters the product with equal standing.

### Category grouping (K/I/B/S)?

**CONFIRMED ABSENT.** There is no category concept anywhere in `fusion.py`. Signals are grouped only by actor pair, never by evidence category. `contributing_link_types` is a flat comma-joined string of raw `link_type` values (`fusion.py:78`).

### Duplicate / non-independent evidence (EC-24) — CONFIRMED BROKEN

`confidences` at `fusion.py:63` uses **every** row, while `link_types` at `fusion.py:64` is deduplicated. Because identity_graph writes **both** the PGP link and the wallet link with the *same* `link_type='shared_identifier'`, a pair that shares PGP *and* wallet (e.g. DarkFox↔DarkFox_v2) produces **two** rows, both `'shared_identifier'`, with confidences `[95, 90]`. Fusion multiplies both into the noisy-OR:
```
1 - (1-0.95)(1-0.90) = 1 - (0.05)(0.10) = 0.995 → 99%
```
…yet `signal_count = 1` (link_types deduped), so the dashboard's `[BOOSTED]` indicator does *not* fire (`fusion.py:103`) even though the score *was* boosted by double-counting. **The two identifiers are not independent evidence** — they may come from the same leaked keyring / same person reusing both — but noisy-OR treats them as independent and inflates confidence accordingly. There is no independence grouping and no deduplication of correlated evidence.

### Output — score, label, or both?

A bare numeric `fused_confidence` (int 0–100) plus `contributing_link_types` (string), `signal_count` (int), and `evidence_summary` (concatenated evidence strings, `fusion.py:81-82`). **No tier label, no explanation text, no limitation/caveat field, no confidence interval.**

### Versioning?

**CONFIRMED ABSENT.** Neither the score model nor the config is versioned. `fused_links` has `created_at` (write time) only. Re-running with a changed formula silently overwrites via `INSERT OR REPLACE ... UNIQUE(actor_a, actor_b)` (`db_setup.py:89`) with no record of which formula produced a score.

### EC-23 — what happens when a category has no evidence? (THE KEY QUESTION)

Because there is **no category model at all**, the literal answer is: absent signals are **skipped**, not zeroed. The noisy-OR product starts at `prob_not_linked = 1.0` and only multiplies over confidences that are physically present (`fusion.py:67-69`). A signal that does not exist contributes no factor — it neither raises nor lowers the score.

Two consequences at the pair level:
- A pair with **zero** evidence never enters `pair_links` (it has no rows), so it produces **no `fused_links` row at all** — it is absent from output, not scored 0.
- A pair with **one weak** signal (say a lone 40% semantic link) produces a `fused_links` row at 40%.

So the current code *can* mechanically distinguish "unevidenced" (no row) from "weakly evidenced" (a low-score row) — but only by the *absence* of a row, which is a fragile, implicit signal with no explicit "insufficient evidence" state.

### Analysis: What breaks if we keep this

Grounded in `fusion.py:63-76`:

1. **It cannot represent contradicting evidence.** Noisy-OR is monotonically increasing in every input — each additional signal can only push the score **up** (`fusion.py:68-69`). There is no term that can *lower* confidence. An analyst rejection (link_feedback `'rejected'`) or a negative/exculpatory signal has no path into the score. A pair with one real link and three refuted ones scores *higher* than a pair with one real link.

2. **It double-counts non-independent evidence** (EC-24, above). Two facets of the same identity (`shared_identifier` PGP + wallet) both enter the product because `confidences` is not deduplicated by independence (`fusion.py:63`). Noisy-OR's independence assumption is violated, so the 99% is not a calibrated probability — it is an artefact of counting one identity twice.

3. **Unevidenced vs weakly-evidenced is distinguishable only by row absence.** There is no explicit floor or "insufficient evidence" tier. Downstream consumers must treat "no fused row" as "not attributed"; the dashboard happens to do this, but nothing enforces it. A single 40% semantic-similarity link — the weakest, most over-labelled signal in the system — surfaces as a positive 40% attribution with no caveat.

4. **The 99% cap is cosmetic** (`fusion.py:74-76`). With hardcoded 95/90 inputs, any two shared-identifier facets already saturate to 99. The cap hides saturation rather than calibrating it, so the top of the scale is uninformative — many genuinely different evidence strengths all read "99%".

5. **No categories means correlated signals are never collapsed.** A proper fusion needs to combine *within* a category (take the strongest, or model correlation) and apply noisy-OR *across* independent categories (K/I/B/S). The current flat product does neither.

### Security concerns

- Score inflation from double-counted identifiers presents unreliable 99% attributions to analysts (`fusion.py:63`).
- Monotonic model cannot down-weight analyst-rejected links, so the feedback loop (dashboard) can never lower a fused score (`fusion.py:66-72`).

### Data-provenance gaps

- `evidence_summary` is a flattened string, not structured provenance; it inherits the missing capture/source/hash from the upstream links (`fusion.py:81-82`).
- No score-model version stored, so a fused score is not reproducible (`fusion.py:87-91`).

### Adapter required

A fusion redesign (not a thin adapter) that: classifies each evidence unit into a category (K/I/B/S) via the enum in `docs/indicator-types.md`; combines within-category with independence-aware logic (dedupe correlated identifiers, EC-24); applies noisy-OR across categories; supports a signed/negative or veto term so contradicting evidence and analyst rejections can lower the score; emits an explicit "insufficient evidence" state (EC-23) rather than relying on row absence; and stamps a `score_model_version`.

---

## Module: dashboard

| Field | Finding |
|---|---|
| File path | `dashboard.py` |
| Entry point | Top-level Streamlit script (`streamlit run dashboard.py`). No `main()`; executes top to bottom. |
| Language / runtime | Python 3 + Streamlit, pandas, sqlite3. |
| Input format | Direct SQL against `scraper/darkweb_intel.db` via `query_df` / `query_rows` helpers (`dashboard.py:43-54`). |
| Output format | Rendered HTML/Streamlit UI; CSV & JSON download buttons. |
| Dependencies | `streamlit`, `sqlite3`, `pandas`, `os`, `json`, `datetime`; imports `feedback_stats.get_feedback_stats` lazily (`dashboard.py:217`). |
| Current test data | Reads live DB. |
| Test coverage | **None.** |

### Views that exist

Only **two screens**, switched by `st.session_state.selected_actor` (`dashboard.py:246-256`) — not Streamlit multipage:

- **Sidebar** (`dashboard.py:190-229`): quick-stat metrics (actors, posts, relationship links, infra matches) and a "Signal Reliability" block driven by `feedback_stats` (`dashboard.py:213-224`).
- **Screen 1 — Search / Home** (`dashboard.py:516-639`): text search across handle/category/pgp/wallet/source (`dashboard.py:554-558`), category selectbox, last-seen date range; results list with per-actor buttons; bulk CSV/JSON export.
- **Screen 2 — Actor Profile** (`dashboard.py:262-509`): header, identifiers, **Linked Personas** (fusion display + shared-identifier links + stylometric links with confirm/reject buttons), **Infrastructure Correlation**, **Posts/Activity**, per-actor CSV/JSON export.

### Authentication / roles

**CONFIRMED ABSENT.** No login, no session auth, no role check anywhere. `st.set_page_config` and page logic run for anyone who can reach the Streamlit port. Any viewer can submit analyst feedback.

### What is shown when a link is displayed

More than a bare score:
- Shared-identifier card: other actor, confidence emoji + `Confidence: N%`, and the `evidence` text (`dashboard.py:351-356`).
- Stylometric card: same, **plus** an explicit caveat line: *"⚠️ This pair shares NO PGP key or wallet — this link was found through AI stylometric analysis only."* (`dashboard.py:381`).
- Fusion display: `Multi-Signal Fused Score: N%` with signal count and contributing types (`dashboard.py:324-327`).

### Graph view / timeline / export

- **Graph view: NONE.** `networkx`/`pyvis` are in `requirements.txt` but `dashboard.py` imports neither and renders no graph. (The pyvis graph is a *planned* P1 item — `docs/Implementation_Plan.md:96`.)
- **Timeline: NONE.** Posts are listed by timestamp DESC (`dashboard.py:438-441`) but there is no timeline visualisation.
- **Export: YES.** Per-actor CSV (`dashboard.py:494-499`) and JSON (`dashboard.py:503-509`); bulk filtered CSV/JSON (`dashboard.py:621-639`).

### Disclosure / limitation text

The **only** limitation text shown anywhere is the per-stylometric-card caveat at `dashboard.py:381`. There is **no global disclaimer**, no statement that scores are prototype/uncalibrated, no note that shared identifiers may be non-independent, and no caveat on the fusion score. The `'stylometric'` links are still headed "AI Stylometry" (`dashboard.py:369`), overstating the semantic-similarity measurement (see stylometry finding).

### How it queries the DB

**Direct SQL inline in the UI layer.** `query_df` and `query_rows` are thin `pandas.read_sql_query` / cursor wrappers (`dashboard.py:43-54`); SQL strings are written inline throughout the render code (e.g. `dashboard.py:310-315`, `330-335`, `465-468`). No repository/DAO abstraction, no ORM. The connection is cached with `check_same_thread=False` (`dashboard.py:38`).

### Security concerns

- No authentication or role gating — anyone reaching the app can view all intelligence and write feedback (`dashboard.py:190+`, `record_feedback`).
- `unsafe_allow_html=True` is used to inject actor-derived strings (handles, evidence, **post text**) into HTML without escaping (`dashboard.py:446-451` renders `post['text']` raw) — a stored-XSS vector if any post/handle contains markup. Data is synthetic today, but the scraper feeds this table.
- Search uses parameterised `LIKE` (`dashboard.py:559-560`) — no SQL injection there; the risk is the raw-HTML rendering, not the queries.

### Data-provenance gaps

- The UI can only show what the tables hold; with no provenance columns upstream, an analyst cannot click through to a source capture or verify an evidence claim.

### Adapter required

A presentation adapter/refactor that: adds a global limitation/disclaimer banner and a per-score caveat sourced from the fusion `limitation` field; escapes all actor-derived text before HTML injection; and (Phase-later) adds the graph view and provenance drill-down once evidence carries capture IDs.

---

## Module: feedback (feedback_stats.py + dashboard write path)

| Field | Finding |
|---|---|
| File path | `feedback_stats.py` (read/aggregate); write path is `dashboard.record_feedback` (`dashboard.py:77-85`). |
| Entry point | `get_feedback_stats()` and `print_feedback_summary()` (`feedback_stats.py:16`, `:65`); CLI at `:86`. |
| Language / runtime | Python 3, stdlib `sqlite3`, `os`. |
| Input format | `link_feedback` JOIN `relationship_links` on `link_id`, filtered `link_source='relationship_links'` (`feedback_stats.py:32-42`). |
| Output format | Dict per `link_type`: `total`, `confirmed`, `rejected`, `reliability_pct` (`feedback_stats.py:54-59`). |
| Dependencies | stdlib only. |
| Current test data | Empty until an analyst clicks a button. |
| Test coverage | **None.** |

### What a confirm/reject writes, and where

`record_feedback` runs `INSERT INTO link_feedback (link_id, link_source, feedback) VALUES (?, ?, ?)` (`dashboard.py:81-84`). `feedback` is the literal `'confirmed'` or `'rejected'` (`dashboard.py:359`, `:365`, `:387`, `:391`); `link_source` is always `'relationship_links'`.

### Is a reason/note required? (EC-26)

**No.** The `link_feedback` table *has* an `analyst_note` column (`db_setup.py:98`), but `record_feedback` **never writes it** (`dashboard.py:81-84`) — the column is always NULL. No reason is captured or required. EC-26 confirmed absent despite the column existing.

### Append-only or in-place?

**Append-only.** Every click is a new `INSERT` (`dashboard.py:82`); there is no `UPDATE`/`DELETE` of feedback rows anywhere. Clicking Confirm then False-Positive on the same link writes **two** rows, both retained.

### Is the acting user recorded?

**No.** `link_feedback` has no analyst/user identity column (`db_setup.py:93-100`) and `record_feedback` records none. Combined with the missing dashboard auth, feedback is fully anonymous.

### Is a timestamp recorded?

**Yes.** `submitted_at TEXT DEFAULT CURRENT_TIMESTAMP` (`db_setup.py:99`). SQLite `CURRENT_TIMESTAMP` is **UTC** in `YYYY-MM-DD HH:MM:SS` form (EC-17). Note the same UTC default is used on every table's `created_at`/`matched_at`.

### Can a decision be reverted, and is history preserved? (EC-14)

History **is** preserved (append-only), but there is **no revert semantics**. There is no way to mark a prior decision superseded, and no "current state" resolution: `get_feedback_stats` counts *all* rows (`feedback_stats.py:34-42`), so a Confirm followed by a Reject counts as one confirmed **and** one rejected, distorting `reliability_pct = confirmed/total` (`feedback_stats.py:52`). A user cannot correct a mis-click except by adding an opposing row, which pollutes the reliability metric rather than replacing the earlier vote.

### Security concerns

- Anonymous, unauthenticated, unlimited feedback writes (no user, no rate limit) let anyone skew `reliability_pct` (`dashboard.py:77-85`).
- Fused links have **no feedback path** — `record_feedback` only ever tags `link_source='relationship_links'`, so the fusion score can never receive or reflect analyst judgement.

### Data-provenance gaps

- No actor/analyst identity and no note means a confirmed link cannot be attributed to a reviewer or justified — the audit trail records *that* someone voted, never *who* or *why*.

### Adapter required

A feedback adapter that: makes writes carry `analyst_id` and an optional-but-recommended `analyst_note` (EC-26); models revert as a new append that supersedes prior votes with an explicit "current decision" resolution (EC-14) so `reliability_pct` counts one vote per link per analyst; and extends the feedback path to fused links so analyst judgement can feed back into scoring.

---

## Module: database (db_setup.py)

**Source:** `db_setup.py:25-107` — a single `executescript`. No migration framework, no ALTER paths; schema is idempotent via `CREATE TABLE IF NOT EXISTS`.

### Table-by-table inventory

| Table | Columns (name : type) | Keys / constraints | Indexes | Written by | Read by |
|---|---|---|---|---|---|
| `actors` | handle:TEXT, category:TEXT, source:TEXT, status:TEXT, last_seen:TEXT, pgp_fingerprint:TEXT, wallet_address:TEXT | PK(handle); no FK | — | scraper (Dev A) | identity_graph, dashboard |
| `posts` | id:INTEGER, handle:TEXT, timestamp:TEXT, text:TEXT | PK(id) AUTOINCREMENT; FK(handle→actors) | idx_posts_handle | scraper (Dev A) | stylometry, dashboard |
| `relationship_links` | id:INTEGER, actor_a:TEXT, actor_b:TEXT, link_type:TEXT, evidence:TEXT, confidence_score:INTEGER, created_at:TEXT | PK(id); NOT NULL a/b/type/evidence/conf; CHECK link_type IN ('shared_identifier','stylometric'); CHECK conf 0–100; FK a,b→actors; **UNIQUE(actor_a,actor_b,link_type)** | idx_links_actor_a, idx_links_actor_b | identity_graph, stylometry | fusion, dashboard, feedback_stats |
| `infra_links` | id:INTEGER, onion_address:TEXT, clearnet_host:TEXT, evidence:TEXT, confidence_score:INTEGER, matched_at:TEXT | PK(id); NOT NULL onion/clearnet/evidence/conf; CHECK conf 0–100; **no FK, no UNIQUE** | — | match_infra (Dev A) | dashboard |
| `actor_infra_map` | handle:TEXT, onion_address:TEXT | **no PK**; FK(handle→actors), FK(onion_address→infra_links.onion_address) | — | match_infra (Dev A), scraper | dashboard |
| `fused_links` | id:INTEGER, actor_a:TEXT, actor_b:TEXT, fused_confidence:INTEGER, contributing_link_types:TEXT, signal_count:INTEGER, evidence_summary:TEXT, created_at:TEXT | PK(id); NOT NULL a/b/conf/types/count/summary; CHECK conf 0–100; FK a,b→actors; **UNIQUE(actor_a,actor_b)** | idx_fused_actors | fusion | dashboard |
| `link_feedback` | id:INTEGER, link_id:INTEGER, link_source:TEXT, feedback:TEXT, analyst_note:TEXT, submitted_at:TEXT | PK(id); NOT NULL link_source/feedback; CHECK feedback IN ('confirmed','rejected'); **no FK on link_id**; no UNIQUE | — | dashboard.record_feedback | feedback_stats |

### Table count — verified

**7 user tables** created by `db_setup.py` (`actors`, `posts`, `relationship_links`, `infra_links`, `actor_infra_map`, `fused_links`, `link_feedback`). The plan's "7" is correct. `sqlite_master` will report **8** because `AUTOINCREMENT` triggers SQLite's internal `sqlite_sequence` table — that is what the summary print at `db_setup.py:117-122` will list. `docs/Backend_Schema.md` documents only 5 (it predates `fused_links` and `link_feedback`) and is stale.

### Keys — PK / FK / neither

- **Have a PK:** actors (handle), posts, relationship_links, infra_links, fused_links, link_feedback (all surrogate `id` except actors).
- **Have FKs:** posts, relationship_links, actor_infra_map, fused_links. (Note SQLite does **not** enforce FKs unless `PRAGMA foreign_keys=ON`, which no module sets — so all FKs are advisory only.)
- **Neither PK nor a usable identity:** `actor_infra_map` has **no primary key at all** — duplicate `(handle, onion_address)` rows are allowed; `match_infra` guards against this in code, not schema.
- `link_feedback.link_id` is **not** a declared FK; `feedback_stats` joins it to `relationship_links.id` by convention only (`feedback_stats.py:39`).

### UNIQUE constraints — idempotency

- `relationship_links`: `UNIQUE(actor_a, actor_b, link_type)` (`db_setup.py:56`) — makes identity/stylometry re-runs idempotent via `INSERT OR IGNORE`. **However**, because both PGP and wallet links share `link_type='shared_identifier'`, only **one** of them can persist per pair — the second `INSERT OR IGNORE` is silently dropped. So a pair sharing *both* PGP and wallet stores only the first-written shared-identifier row, and the fusion double-count (EC-24) depends on both rows existing. *(This means in practice the DarkFox PGP+wallet double-count is suppressed by the UNIQUE constraint, while stylometric+shared_identifier on the same pair is not. Worth verifying at runtime — marked UNVERIFIED pending a live DB run.)*
- `fused_links`: `UNIQUE(actor_a, actor_b)` (`db_setup.py:89`) — one fused row per pair; `INSERT OR REPLACE` overwrites.
- `infra_links`, `actor_infra_map`, `link_feedback`: **no UNIQUE** — re-runs and repeat clicks duplicate rows. Idempotency is impossible for these three at the schema level.

### Provenance columns

**CONFIRMED ABSENT across every table.** No capture ID, no source URL, no content/evidence hash, no collector identity anywhere in the schema (`db_setup.py:25-107`). The closest fields are the free-text `evidence`/`evidence_summary` strings and `actors.source` (a market name, not a capture reference).

### Timestamps (EC-17)

- `created_at` / `matched_at` / `submitted_at` all `TEXT DEFAULT CURRENT_TIMESTAMP` → SQLite writes **UTC** as `YYYY-MM-DD HH:MM:SS`.
- `actors.last_seen` and `posts.timestamp` are free-text (`TEXT`) populated from source data (`YYYY-MM-DD` and ISO-8601 respectively in the sample) — **no timezone**, no validation.
- These are write-time stamps, not observation/capture times — see provenance gap.

### Audit / history table

**None.** There is no audit-event or version-history table. `link_feedback` is the only append-only log, and it tracks votes, not entity/link mutations.

### Mapping existing tables → canonical schema

| Existing table | Canonical target | Verdict |
|---|---|---|
| `actors` | `entities` | **extend** — add provenance, normalised identifiers, roles |
| `posts` | `captures` + `evidence_units` | **extend/split** — posts are raw captures; needs capture ID, source URL, hash |
| `relationship_links` | `candidate_links` | **extend** — add `indicator_type`, category, provenance, role; widen `link_type` CHECK |
| `fused_links` | `candidate_links` (scored) + `candidate_link_versions` | **replace** — recompute under categorised fusion; add version rows |
| `link_feedback` | `audit_events` | **replace** — add analyst identity, note, supersede semantics |
| `infra_links` | `evidence_units` (I-category) | **extend** — add provenance, UNIQUE, actor linkage |
| `actor_infra_map` | (join into `evidence_units`/`candidate_links`) | **replace** — no PK; fold into evidence linkage |
| *(none)* | `candidate_link_versions` | **new build** — score history does not exist |
| *(none)* | `audit_events` | **new build** — no mutation audit trail exists |
| *(none)* | `timeline_events` | **new build** — no timeline table exists |

### Security concerns

- FKs are declared but unenforced (no `PRAGMA foreign_keys=ON`) — orphaned links are possible.
- No UNIQUE on `link_feedback`, `infra_links`, `actor_infra_map` — duplicate/replayed rows silently accumulate.

### Data-provenance gaps

- Zero provenance columns system-wide; no content hashes make no evidence tamper-evident.
- No audit/history table means link and score changes are unrecoverable.

### Adapter required

Schema is Dev B's to extend in a later phase (not now — HARD CONSTRAINT 1). The audit records the target mapping above; the build will add provenance columns, an `audit_events` table, `candidate_link_versions`, and `timeline_events`, and widen the `relationship_links.link_type` CHECK to the full enum.

---

## EC-40 — synthetic content verification

**Files checked:** `sample_data/personas.json` (10 personas), `sample_data/posts.json` (24 posts). These are the only files under `sample_data/`. Method: charset + base58check checksum validation of every wallet (script run during audit); manual read of every PGP fingerprint, `.onion`, and post body.

### `sample_data/personas.json` — **NEEDS REVIEW**

**Concern: two wallet strings are checksum-valid, real-format Bitcoin mainnet addresses**, not obviously-fake placeholders:

| Handle | Wallet | Result |
|---|---|---|
| Nightshade99 | `1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2` (`personas.json:38`) | **base58check VALID** (P2PKH). This is a widely-circulated example/test address from Bitcoin documentation and libraries — a real, format-correct mainnet address. |
| GhostVendor | `3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5` (`personas.json:28`) | **base58check VALID** (P2SH). Checksum passes — a well-formed mainnet address. |

The remaining wallets are safe placeholders — they **fail** validation and cannot be real addresses:
- `bc1q...` addresses for DarkFox/DarkFox_v2, cipherqueen, moneymule_88 contain characters outside the bech32 charset (`b`, `i`, `o`) → invalid.
- `1FghijK2LmnoPqrsTuvwXyzABC3DEfGhi4J` (pillcartel_x) and `1ViperX8888…` (ViperX) fail the base58check checksum → invalid.
- `3GhIjKlmNoPqRsTuVwXyZ…` (redroom_admin) contains `I`/`l`, illegal in base58 → invalid.

**PGP fingerprints:** all 10 are hand-patterned 40-hex-digit strings (e.g. `1122 33AA BBCC DD44 …`, `personas.json:27`). None is an exported key block; none resembles a real published fingerprint. **SAFE.**

**Other:** no `.onion` addresses, no personal data, no illegal material. The `note` fields explicitly describe each persona as a test case.

**Recommended remediation (do not apply now — HARD CONSTRAINT 1):** replace the two checksum-valid wallets with deliberately invalid strings (e.g. append an out-of-charset character or corrupt the checksum) so no address in the demo can resolve to a live mainnet address. This is what lets the team state honestly that the demo contains no live crypto identifiers.

### `sample_data/posts.json` — **SYNTHETIC — SAFE**

24 posts of fictional dark-web-marketplace marketing prose (e.g. GhostVendor/Nightshade99 vendor patter, `posts.json:2-8`; ViperX "zero day exploits" flavour text, `posts.json:27-30`). Verified:
- No real credentials, data dumps, exploit code, or operational instructions — the "zero day" / "credential dumps" mentions are narrative flavour, not actual material.
- No `.onion` addresses, no wallet/PGP strings, no URLs.
- No personal data (no real names, emails, handles tied to real people).
- The stylistic near-duplication between rebrand pairs (GhostVendor↔Nightshade99, ViperX↔ViperX_Reborn) is deliberate test scaffolding for the stylometry module.

**Verdict table:**

| File | Verdict | Notes |
|---|---|---|
| `sample_data/personas.json` | **NEEDS REVIEW** | 2 checksum-valid BTC mainnet addresses (Nightshade99 P2PKH, GhostVendor P2SH); replace with invalid placeholders. PGP/other content synthetic. |
| `sample_data/posts.json` | **SYNTHETIC — SAFE** | Fictional prose; no real identifiers, no illegal material, no personal data. |

---
