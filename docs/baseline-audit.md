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
