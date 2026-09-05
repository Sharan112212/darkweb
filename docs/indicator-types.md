# Indicator Type Enum — SIH26151 (contract)

**Branch:** feat/branch-0-baseline-audit
**Owner:** Dev B (scoring & interface lane)
**Status:** DRAFT contract — **this unblocks Dev A.** Every module writes evidence tagged with one `indicator_type` from this enum; the category classifier and fusion engine are written once against it.

**Categories:** `K` = cryptographic / hard identifier · `I` = infrastructure · `B` = behavioural · `S` = semantic / stylistic.

---

## What the existing code actually emits today

Derived by reading the source (not the plan). The current codebase writes only **three** distinct evidence labels:

| Real string in code | Where | Table | Maps to enum |
|---|---|---|---|
| `'shared_identifier'` (PGP branch) | `identity_graph.py:46` (conf 95, `identity_graph.py:18`) | `relationship_links` | `pgp_fingerprint` (K) |
| `'shared_identifier'` (wallet branch) | `identity_graph.py:72` (conf 90, `identity_graph.py:19`) | `relationship_links` | `wallet_address` (K) |
| `'stylometric'` | `stylometry.py:127` (conf = rescaled cosine, `stylometry.py:120`) | `relationship_links` | `semantic_similarity` (S) |
| `'SSL certificate fingerprint match'` (evidence text; conf 98) | `infra-matcher/match_infra.py:73` (Dev A) | `infra_links` | `certificate_fingerprint` (I) |

**Two migrations are required** (recorded per-entry below):
1. `'shared_identifier'` is overloaded — it tags **both** PGP and wallet matches. It must split into `pgp_fingerprint` and `wallet_address` so category/role logic can treat them differently.
2. `'stylometric'` is a misnomer — the measurement is SBERT semantic cosine similarity, not authorship stylometry (see `docs/baseline-audit.md` → Module: stylometry). It must be renamed `semantic_similarity`; the name `classical_stylometry` is reserved for a real stylometric signal that does not yet exist.

---

## K — cryptographic / hard identifiers

### `pgp_fingerprint`
- **Category:** K
- **Emitted by:** identity_evidence_adapter (wraps `identity_graph.py`)
- **Currently emitted as:** `'shared_identifier'` in `identity_graph.py:46` (PGP branch), confidence `95` from `identity_graph.py:18`
- **Default weight:** 0.95
- **Description:** Same PGP fingerprint observed across two personas.
- **Note:** requires `indicator_role` to distinguish `key_published` from `verified_signature` (EC-10). Normalise the fingerprint (strip whitespace, upper-case) before comparison (EC-11).

### `wallet_address`
- **Category:** K
- **Emitted by:** identity_evidence_adapter (wraps `identity_graph.py`)
- **Currently emitted as:** `'shared_identifier'` in `identity_graph.py:72` (wallet branch), confidence `90` from `identity_graph.py:19`
- **Default weight:** 0.90
- **Description:** Same cryptocurrency address observed across two personas.
- **Note:** requires `indicator_role` to distinguish personal / shared-service / escrow / mixer wallets (EC-09) — a mixer or exchange deposit address must not link actors at 0.90. Record chain/network; today it is undistinguished.

### `contact_identifier`
- **Category:** K
- **Emitted by:** not yet built
- **Currently emitted as:** — (nothing emits this)
- **Default weight:** 0.85
- **Description:** Shared reachable contact handle (email, Jabber/XMPP, Session ID, Telegram, ICQ).
- **Note:** weight depends on uniqueness of the channel; role field should flag disposable vs persistent identifiers.

### `alias`
- **Category:** K
- **Emitted by:** not yet built
- **Currently emitted as:** — (nothing emits this)
- **Default weight:** 0.50
- **Description:** Reuse of the same handle/nickname across sites.
- **Note:** weakest K signal — aliases are guessable and reusable. Requires case-fold + Unicode (NFKC) + whitespace normalisation before match (EC-11).

---

## I — infrastructure

### `certificate_fingerprint`
- **Category:** I
- **Emitted by:** infra_evidence_adapter (wraps `infra-matcher/match_infra.py`, Dev A)
- **Currently emitted as:** row in `infra_links` with evidence `'SSL certificate fingerprint match'` and `confidence_score=98` (`infra-matcher/match_infra.py:73`; value per `docs/Implementation_Plan.md:62`)
- **Default weight:** 0.98
- **Description:** Identical TLS/SSL certificate SHA-256 fingerprint on an onion service and a clearnet host.
- **Note:** currently written to `infra_links`, **not** `relationship_links`, and **not consumed by fusion** — must be routed into the evidence stream so it can be fused.

### `infrastructure_match`
- **Category:** I
- **Emitted by:** infra_evidence_adapter (generic infra correlation)
- **Currently emitted as:** — (generic bucket; specific certificate matches use `certificate_fingerprint`)
- **Default weight:** 0.85
- **Description:** Correlated hosting infrastructure (shared IP, ASN, server banner) short of an exact certificate match.
- **Note:** umbrella value for infra signals that are not one of the specific OnionScan types below.

### `onionscan_analytics_id`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.90
- **Description:** Same analytics/tracking ID (e.g. Google Analytics UA) across services.

### `onionscan_exif_leak`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.80
- **Description:** Shared EXIF metadata (camera, GPS, author) in images across services.

### `onionscan_server_status`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.55
- **Description:** Correlated server status / mod_status or uptime fingerprint.

### `onionscan_ssh_key`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.92
- **Description:** Same SSH host key fingerprint across services.

### `onionscan_certificate`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.95
- **Description:** OnionScan-discovered TLS certificate reuse (distinct from the infra-matcher's direct compare).
- **Note:** overlaps `certificate_fingerprint`; keep separate so the collector of record is traceable.

### `onionscan_open_directory`
- **Category:** I
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.60
- **Description:** Shared open-directory listing / identical file tree exposed across services.

---

## B — behavioural (nothing produces these until Dev A's Phase 4)

### `posting_time_pattern`
- **Category:** B
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.55
- **Description:** Correlated activity timing / timezone / diurnal rhythm across personas.
- **Note:** `posts.timestamp` is present (`posts.json`) so the raw signal is available; nothing computes it yet.

### `vocabulary_overlap`
- **Category:** B
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.50
- **Description:** Distinctive shared vocabulary / rare-term overlap (jargon, slang, misspellings).
- **Note:** distinct from `semantic_similarity` — this is lexical feature overlap, not embedding cosine.

### `template_match`
- **Category:** B
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.65
- **Description:** Reused post/listing template or boilerplate structure across personas.

### `persona_migration`
- **Category:** B
- **Emitted by:** not yet built
- **Currently emitted as:** —
- **Default weight:** 0.70
- **Description:** Temporal handoff pattern — one persona goes silent as another appears with continuity cues ("operations resumed under a new listing name").
- **Note:** the sample data is built for this (DarkFox→DarkFox_v2 note, `personas.json:20`), but no module detects it.

---

## S — semantic / stylistic

### `semantic_similarity`
- **Category:** S
- **Emitted by:** stylometry_evidence_adapter (wraps `stylometry.py`)
- **Currently emitted as:** `'stylometric'` in `stylometry.py:127`, confidence = `int(round(sim*100))` (`stylometry.py:120`), threshold `0.75` (`stylometry.py:24`)
- **Default weight:** 0.60
- **Description:** High SBERT (`all-MiniLM-L6-v2`) cosine similarity between two personas' concatenated post embeddings.
- **Note (MIGRATION):** old string `'stylometric'` → new `semantic_similarity`. This measures topic/register similarity, **not** authorship; weight is deliberately modest (0.60) to reflect that. Gate on minimum corpus size and strip boilerplate before trusting (EC-19/EC-21). The UI heading "AI Stylometry" (`dashboard.py:369`) must be updated to match.

### `classical_stylometry`
- **Category:** S
- **Emitted by:** not yet built
- **Currently emitted as:** — (no true stylometry exists in the codebase)
- **Default weight:** 0.70
- **Description:** Authorship attribution from function-word frequencies, character n-grams, punctuation and idiolect features.
- **Note:** reserved name. When built, it — not `semantic_similarity` — is the signal that legitimately supports "same author" language.

---

## Migration summary (old → new)

| Old literal (in code) | File:line | New `indicator_type` | Category |
|---|---|---|---|
| `'shared_identifier'` (PGP) | `identity_graph.py:46` | `pgp_fingerprint` | K |
| `'shared_identifier'` (wallet) | `identity_graph.py:72` | `wallet_address` | K |
| `'stylometric'` | `stylometry.py:127` | `semantic_similarity` | S |
| `infra_links` cert match (conf 98) | `infra-matcher/match_infra.py:73` | `certificate_fingerprint` | I |

The `relationship_links.link_type` CHECK constraint (`db_setup.py:50`) currently allows only `('shared_identifier','stylometric')`. It must be widened to the enum above when the schema is extended (later phase — not in this audit branch).

---

## Deviation — why the enum includes values nothing currently produces

Defining the complete enum in Phase 0 — including behavioural and classical-stylometry values — lets the category classifier be written once against a stable enum. Without it, each new signal branch forces an edit to the classifier, producing a merge conflict per branch. This is a deliberate deviation from the master plan's branch ordering.
