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
