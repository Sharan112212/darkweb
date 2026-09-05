# SIH26151 — Analyst User Guide

This guide provides step-by-step instructions for authorized analysts using the Dark-Web Threat Actor Attribution Platform.

---

## 1. Getting Started

### Accessing the Platform
- **Dashboard:** Open `http://localhost:8501` in your browser (Streamlit UI).
- **API Docs:** Visit `http://localhost:8000/docs` for interactive Swagger documentation.

### Understanding Your Role
| Role | Permissions |
|---|---|
| **Viewer** | Search entities, view graph topology, view redacted evidence summaries |
| **Analyst** | Full evidence access, create cases, submit link decisions (accept/reject/defer), add notes, export reports |
| **Reviewer** | Approve or reject case exports and policy changes |
| **Admin** | Manage source allowlists, toggle kill-switch, trigger graph reconciliation, view audit logs |

---

## 2. Searching for Threat Actors

1. Navigate to the **Search** tab on the dashboard.
2. Enter an alias, PGP fingerprint fragment, wallet address, or keyword.
3. Results display matching entities with their current association tier and link count.
4. Click any entity name to open the **Actor Profile** page.

> **Empty Results:** The system distinguishes between "no matching evidence collected", "source unavailable", "search restricted by role", and "data exists but is redacted". Check the `absence_reason` field.

---

## 3. Reading Actor Profiles

Each profile displays:
- **Entity Summary:** Canonical name, type (Persona/Service/Infrastructure), and entity ID.
- **Candidate Links:** All associated entity pairs with:
  - **Tier:** `insufficient_evidence` → `unresolved` → `possible_association` → `likely_same_actor` → `observed_technical_identity`
  - **Score:** Numerical confidence (0.00–1.00)
  - **Category Breakdown:** K (Cryptographic), I (Infrastructure), B (Behavioral), S (Stylometric) contributions
  - **Limitations:** Explicit caveats explaining what the score cannot prove

---

## 4. Using the Evidence Drawer

Click any link/edge in the graph or profile to open the **Evidence Drawer**. It shows the full evidence chain:

```
Module/Source → Observed indicator → Linked entities → Dates → Reliability → Confidence contribution → Caveat
```

Each evidence record includes:
- `evidence_id` and `capture_id` for traceability
- `raw_evidence_hash` (SHA-256) for integrity verification
- `indicator_role` (e.g., `key_published` vs `verified_signature`)
- `model_metadata` (scoring model version, corpus statistics)
- `limitations` (explicit caveats such as "Published key is not proof of key control")

---

## 5. Navigating the Graph Explorer

- **Default view:** 2-hop ego graph centered on the selected actor.
- **Edge styles:**
  - Dotted grey: `possible_association`
  - Neutral: `unresolved`
  - Amber: `likely_same_actor`
  - Green: `observed_technical_identity`
  - Hidden by default: `rejected` links
- **Controls:** Adjust depth (1–5 hops), minimum score filter, and date range.
- **Truncation:** Large graphs are capped at 100 nodes with a `truncated: true` indicator.

---

## 6. Making Analyst Decisions

To accept, reject, or defer a candidate link:

1. Click the link in the graph or profile to open the Evidence Drawer.
2. Review all contributing evidence, category breakdown, and limitations.
3. Click **Accept**, **Reject**, or **Defer**.
4. **Enter a mandatory note** explaining your reasoning (decisions without notes are blocked).
5. Submit. The decision creates:
   - An immutable `CandidateLink` version record
   - An `AuditEvent` entry in the append-only audit log
   - A `TimelineEvent` for the link's history

> **Important:** Decisions are reversible. A rejected link can be re-accepted by creating a new version. Full history is preserved — no destructive merges.

---

## 7. Using the Timeline Explorer

The Timeline tab shows chronological events for an actor:
- Evidence observation dates
- Link creation and state changes
- Analyst decisions
- Persona migration events (e.g., handle rebrands)

**Time confidence labels:**
- `exact` — Timestamp verified from source metadata
- `approximate` — Derived from source-claimed time (may be forged)
- `uncertain` — Only capture timestamp available

---

## 8. Exporting Case Reports

1. Navigate to **Cases** → **Create Case**.
2. Add entity references and relevant links to the case.
3. Click **Export** and select format: JSON, CSV, or PDF.
4. The export engine creates an **immutable snapshot** freezing the exact versions of all evidence, links, and scoring models at that moment.
5. Every export includes the mandatory disclosure statement and SHA-256 integrity hash.

---

## 9. Understanding Score Caps & Safety Boundaries

The platform enforces strict evidence boundaries to prevent false positives:

| Rule | Effect |
|---|---|
| Text/stylometry alone | Capped at `possible_association` (≤ 0.20 contribution) |
| Infrastructure alone | Capped at `possible_association` |
| Shared mixer/escrow wallet | Downweighted; tagged as `shared_service_wallet` |
| Duplicate evidence | Deduplicated via `independence_group_id`; Noisy-OR prevents inflation |
| Tier boundary crossing | Requires ≥ 0.03 margin (hysteresis) to prevent fluctuation |

---

## 10. Mandatory Disclosure

> **"This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation."**

This banner is displayed on the dashboard and included in all exported reports.
