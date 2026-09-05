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
- `db_setup.py` creates **8 tables** (see B0.5), not the 7 the plan assumes.

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
