# App Flow
## Dark Web Threat Actor De-anonymization System — Prototype

This describes the user-facing flow through the dashboard, and the
underlying data flow it depends on.

---

## 1. Data flow (happens before the user opens the app)

```
1. docker compose up          → mock lab live
2. scraper.py                 → actors + posts populated in DB
3. identity_graph.py          → shared_identifier links written
4. stylometry.py              → stylometric links written
5. match_infra.py             → infra_links written
6. streamlit run dashboard.py → app is ready to use
```

Steps 2-5 can be triggered manually in sequence, or wrapped into one
`run_pipeline.py` script that calls each in order — recommended for demo
reliability so you're not running 4 separate commands on camera.

## 2. User flow (what the analyst sees)

### Screen 1 — Search / Home
- A search bar: "Search by handle, category, or identifier"
- A quick-filter row: category dropdown (drugs / arms / hacking / fraud /
  money laundering / stolen data), date range picker
- Below: a results table (handle, category, source, last_seen, # of
  linked actors) for the current filter/search

**User action:** types a handle (e.g. "Nightshade99") or picks a category → clicks a row

### Screen 2 — Actor Profile
- Header: handle, category, source, status, last_seen
- Identifiers block: PGP fingerprint, wallet address (if present)
- **Linked Personas** section, grouped by link type:
  - "Linked via shared identifier" → e.g. DarkFox_v2, confidence 95%, evidence: "shared PGP fingerprint"
  - "Linked via writing style" → e.g. GhostVendor, confidence 82%, evidence: "matching phrasing and structure across posts"
- **Infrastructure** section (if applicable): matched clearnet host, confidence, evidence
- Raw posts list (for the analyst to read the actual evidence themselves, not just trust the score)
- Export button: "Export this actor's profile" (CSV/JSON)

**User action:** reviews the linked personas and evidence, decides whether the attribution lead is worth investigating further

### Screen 3 — Bulk Export
- From the Screen 1 results table, user can select multiple rows (or "select all filtered")
- Click "Export selection" → choose CSV / JSON / PDF report
- File downloads with all selected actors + their links + confidence scores

## 3. Demo walkthrough script (for your video, matches this flow exactly)

1. Open dashboard, show the home screen with all actors loaded
2. Search "DarkFox" → open profile → point out the linked `DarkFox_v2` with 95% confidence, evidence = shared PGP key
3. Go back, search "Nightshade99" → open profile → point out the linked `GhostVendor` with a lower but still clear confidence score, evidence = writing style match, **explicitly say "notice this pair shares no PGP key or wallet — this link was only found through AI stylometric analysis"**
4. Show the infra match result (either in-dashboard or as a script output) for the vulnerable hidden service tracing to its clearnet twin
5. Go to Screen 1, filter by category or date range, select a few rows, export to CSV, briefly show the downloaded file

This walkthrough directly proves G2, G3, and G4 from the PRD on camera, in under 90 seconds.

## 4. Error/edge states to handle (keep simple, but don't ignore)

- Search with no results → show "No matching actors found" instead of a blank/broken page
- Actor with no links → profile page still loads, "Linked Personas" section shows "No links found" instead of erroring
- Export with zero rows selected → disable the export button rather than producing an empty file
