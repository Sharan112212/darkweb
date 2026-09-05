# SIH26151 — Threat Actor Attribution Scoring Methodology

**Document ID:** DOC-SCORING-METHODOLOGY-V1  
**Target Branch:** Branch 3 (Fusion Engine)  
**Status:** Canonical Reference  
**Classification:** Internal Technical Standard  

---

## 1. Executive Summary & Attribution Philosophy

In dark web threat intelligence, correlating disparate personas across markets, forums, and infrastructure carries high operational risk. Commercial platforms frequently suffer from three fundamental defects:
1. **Ad-hoc Heuristics / Additive Scores:** Adding arbitrary weights together allows weak or duplicated signals to inflate confidence artificially.
2. **False Cryptographic Certainty:** Blindly treating shared wallets or public keys as conclusive identity proof ignores shared escrow services, mixers, and recycled credentials.
3. **Black-Box Opacity:** Statistical similarity scores without explainable, auditable attribution breadcrumbs cannot satisfy investigative standards or evidentiary thresholds.

The SIH26151 platform addresses these challenges through an **evidence-first, defensive, explainable fusion architecture**:
- **Probabilistic Fusion (Noisy-OR):** Evaluates observations as independent causal failure mechanisms rather than linear additive scores.
- **Strict Evidence Categorization (K/I/B/S):** Separates cryptographic identity anchors from infrastructure, behavioral, and stylometric observations.
- **Defensive Capping & Guardrails:** Ensures that unverified, stylometric, or text-only evidence cannot establish a high-confidence attribution tier.
- **Independence Group Deduplication:** Eliminates score inflation arising from mirrored sites, reposted dumps, and syndicated dark web content.
- **Boundary Hysteresis:** Prevents confidence tier oscillation near decision boundaries.
- **Immutable Snapshot Versioning:** Preserves complete audit histories for every score calculation, analyst review, and lifecycle transition.

---

## 2. K/I/B/S Category Classification Architecture

Every piece of collected evidence is normalized by ingestion adapters into a canonical `EvidenceUnit`. Before fusion, the `CategoryClassifier` assigns each unit to one of four canonical categories:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       K / I / B / S Categories                              │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│  Category K     │  Category I     │  Category B     │  Category S           │
│  Cryptographic  │  Infrastructure │  Behavioral     │  Semantic/Stylometry  │
│  Hard Anchors   │  Technical Env  │  Activity/Habit │  Linguistic Vectors   │
│  Cap: 1.00      │  Cap: 0.65      │  Cap: 0.65      │  Cap: 0.20            │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

### 2.1 Category Definitions & Caps

1. **Category K: Cryptographic & Hard Identifiers (Cap: 1.00)**
   - Hard identity anchors that uniquely or strongly bind an actor cryptographically.
   - *Signals:* PGP public key fingerprints, cryptocurrency wallet addresses (direct actor wallets), verified handle/alias collisions, and contact handles (Jabber, Tox, Session).
   - *Maximum Contribution:* `1.00` (Uncapped). When verified cryptographically (e.g. verified PGP signature), K evidence can independently reach `observed_technical_identity`.

2. **Category I: Infrastructure Corroboration (Cap: 0.65)**
   - Host, networking, and server configuration artifacts discovered across dark web (.onion) and clearnet environments.
   - *Signals:* Shared SSL/TLS certificate SHA-256 fingerprints, co-hosted services, OnionScan findings (Google Analytics IDs, EXIF metadata leaks, mod_status leaks, SSH host keys, TLS certificates, open Apache/Nginx directories).
   - *Maximum Contribution:* `0.65` (Capped). Infrastructure evidence alone can never exceed `possible_association` because dark web hosts frequently share reverse proxies, CDNs, or standard hosting templates.

3. **Category B: Behavioral & Temporal Signatures (Cap: 0.65)**
   - Patterns in operational tempo, specialized vocabularies, message formatting, and persona lifecycle events.
   - *Signals:* Diurnal posting time histograms, vendor specific jargon/vocabulary overlap, structured listing template hashes, and persona migration/rebranding candidate events.
   - *Maximum Contribution:* `0.65` (Capped). Behavioral patterns can corroborate attribution up to `possible_association`, but cannot substantiate technical identity alone.

4. **Category S: Semantic & Stylometric Analysis (Cap: 0.20)**
   - Natural language processing, embedding cosine similarity (Sentence-BERT / MiniLM), and classical stylometry (lexical diversity, function word frequencies, punctuation profiles).
   - *Signals:* Semantic similarity embeddings, stylometric metrics.
   - *Maximum Contribution:* `0.20` (Strictly Capped). Text similarity is treated strictly as **supporting corroboration**. Under operational guidelines, text similarity alone cannot elevate an attribution beyond `insufficient_evidence` or `unresolved`.

---

### 2.2 Master Indicator Type Mapping Table (18 Canonical Types)

The 18 canonical indicator types defined in `models.enums.IndicatorType` are classified as follows:

| # | IndicatorType Enum Value | Category | Category Name | Default Weight | Description & Rationale |
|---|---|:---:|---|:---:|---|
| 1 | `pgp_fingerprint` | **K** | Cryptographic | 0.95 | Full 40-hex SHA-1 PGP fingerprint match across actor profiles. |
| 2 | `wallet_address` | **K** | Cryptographic | 0.90 | On-chain cryptocurrency address (BTC, XMR) match in direct payment context. |
| 3 | `alias` | **K** | Cryptographic | 0.60 | Normalized exact username match across distinct dark web platforms. |
| 4 | `contact_identifier` | **K** | Cryptographic | 0.85 | Shared direct messaging identifier (e.g., Session ID, Tox ID, Jabber/XMPP). |
| 5 | `certificate_fingerprint` | **I** | Infrastructure | 0.77 | Matching SHA-256 fingerprint of X.509 SSL/TLS certificate on hidden & clearnet twins. |
| 6 | `infrastructure_match` | **I** | Infrastructure | 0.70 | Direct IP, ASN, or server misconfiguration shared between endpoints. |
| 7 | `onionscan_analytics_id` | **I** | Infrastructure | 0.65 | Shared Google Analytics, Matomo, or tracking tag discovered by OnionScan. |
| 8 | `onionscan_exif_leak` | **I** | Infrastructure | 0.60 | Leaked camera serial, software string, or metadata embedded in hosted images. |
| 9 | `onionscan_server_status` | **I** | Infrastructure | 0.55 | Exposed Apache `server-status` or Nginx stub status revealing identical client IPs/paths. |
| 10 | `onionscan_ssh_key` | **I** | Infrastructure | 0.75 | Matching SSH host key fingerprint discovered across dark web endpoints. |
| 11 | `onionscan_certificate` | **I** | Infrastructure | 0.70 | Certificate details extracted via OnionScan crawlers. |
| 12 | `onionscan_open_directory` | **I** | Infrastructure | 0.50 | Matching open directory structure or file hierarchy exposed on servers. |
| 13 | `posting_time_pattern` | **B** | Behavioral | 0.50 | Statistically significant overlap in active hours and UTC timezone bins. |
| 14 | `vocabulary_overlap` | **B** | Behavioral | 0.45 | Distinctive jargon, slang terms, or rare domain-specific n-grams. |
| 15 | `template_match` | **B** | Behavioral | 0.40 | Structural layout, PGP sign-off banner, or listing boilerplate match. |
| 16 | `persona_migration_candidate` | **B** | Behavioral | 0.60 | Temporal succession: Persona A goes dark simultaneously as Persona B appears. |
| 17 | `semantic_similarity` | **S** | Stylometric | 0.18 | Dense embedding cosine similarity computed via SBERT `all-MiniLM-L6-v2`. |
| 18 | `classical_stylometry` | **S** | Stylometric | 0.15 | Lexical statistics: function word frequencies, punctuation ratios, sentence lengths. |

---

## 3. Hierarchical Noisy-OR Probabilistic Mathematical Formula

### 3.1 Theoretical Formulation

Standard additive models ($Score = \sum w_i$) fail because adding independent observations can exceed $1.0$ or over-weight minor signals. Conversely, a simple average ($\frac{1}{n} \sum w_i$) penalizes an actor association for having multiple weak observations alongside a strong cryptographic match.

The SIH26151 engine implements the **Noisy-OR gate** from Bayesian probability theory. The Noisy-OR assumption posits that each piece of independent evidence $E_i$ has an independent probability $w_i = P(\text{Association} \mid E_i)$ of establishing the association. The overall probability of an association given independent signals is the complement of all signals failing to establish the association:

$$P(\text{Association} \mid E_1, E_2, \dots, E_n) = 1 - \prod_{i=1}^n (1 - w_i)$$

Where:
- $w_i \in [0.0, 1.0]$ represents the confidence weight of independent evidence signal $i$.
- $1 - w_i$ represents the probability that signal $i$ is a coincidental or false-positive correlation.
- $\prod (1 - w_i)$ is the joint probability that **all** observed signals are false positives.

### 3.2 Two-Stage Hierarchical Evaluation

To prevent category imbalance, fusion is executed in two stages:

```
Raw Evidence Units: [E1, E2, E3, E4, E5...]
                      │
                      ▼
        Categorization & Deduplication
     (Max weight per independence_group_id)
        ┌──────────┬──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼
     Category K Category I Category B Category S
        │          │          │          │
   Stage 1 Noisy-OR for each category
        │          │          │          │
    Capped K   Capped I   Capped B   Capped S
    (≤ 1.00)   (≤ 0.65)   (≤ 0.65)   (≤ 0.20)
        └──────────┬──────────┴──────────┘
                   ▼
          Stage 2 Noisy-OR
       (Cross-Category Fusion)
                   │
                   ▼
           Score Cap Guardrails
   (Text-only capped at 0.65 if K=0 & I=0)
                   │
                   ▼
       Boundary Hysteresis Filter (±0.03)
                   │
                   ▼
             Final Tier & Link
```

#### Stage 1: Intra-Category Aggregation
For each category $C \in \{K, I, B, S\}$:
1. Group evidence units by `independence_group_id`.
2. Select the maximum confidence weight within each group:
   $$w_{C, g} = \max_{u \in \text{Group}_g} w_u$$
3. Apply Noisy-OR across the unique groups:
   $$Score_{C, \text{raw}} = 1 - \prod_{g \in \text{Groups}_C} (1 - w_{C, g})$$
4. Enforce category contribution cap:
   $$Score_C = \min(Score_{C, \text{raw}}, \text{Cap}_C)$$

#### Stage 2: Cross-Category Fusion
Combine non-zero category scores using Noisy-OR:
$$Score_{\text{fused, raw}} = 1 - \prod_{C \in \{K, I, B, S\}, Score_C > 0} (1 - Score_C)$$

#### Stage 3: Defensive Capping Guardrail
If no cryptographic ($K=0$) and no infrastructure ($I=0$) signals exist:
$$Score_{\text{final}} = \min(Score_{\text{fused, raw}}, 0.65)$$
Otherwise:
$$Score_{\text{final}} = Score_{\text{fused, raw}}$$

---

### 3.3 Step-by-Step Worked Example: ViperX ↔ ViperX_Reborn

Consider the benchmark evaluation pair:
- **Signal 1:** Shared BTC Wallet address (`3GhostVendor...`) $\to$ Category K, weight $0.90$. Group: `indep_wallet`.
- **Signal 2:** SBERT semantic similarity score ($0.85$) $\to$ Category S, weight $0.18$. Group: `indep_sbert`.

**Execution:**
1. **Intra-Category Scores:**
   - Category K: $Score_K = \min(1 - (1 - 0.90), 1.00) = 0.9000$
   - Category S: $Score_S = \min(1 - (1 - 0.18), 0.20) = 0.1800$
   - Categories I and B: $Score_I = 0.0, Score_B = 0.0$
2. **Cross-Category Fusion:**
   $$Score_{\text{fused, raw}} = 1 - ((1 - 0.9000) \times (1 - 0.1800)) = 1 - (0.1000 \times 0.8200) = 1 - 0.0820 = 0.9180$$
3. **Guardrail Check:**
   $K > 0$, so text-only cap does not apply.
   $$Score_{\text{final}} = 0.9180$$
4. **Tier Mapping:**
   $0.9180 \ge 0.90 \implies \mathbf{observed\_technical\_identity}$.
   *Notice the multi-signal boost:* The wallet ($0.90$) alone was at the bottom threshold of technical identity; the corroborating stylometric signal boosts total confidence to $0.9180$, confirming attribution while capturing full explainability.

---

## 4. Independence Group Deduplication (EC-24)

### 4.1 The Vulnerability: Score Inflation from Mirrored Sources
In dark web environments, marketplace forums and leak sites are continuously scraped, mirrored, and archived. A threat actor profile from *Market Alpha* might be mirrored across 15 proxy sites or archived across 5 database backups.

If a naive Noisy-OR model treats 10 identical observations of a single PGP key with weight $0.95$ as independent:
$$1 - (1 - 0.95)^{10} = 1 - (0.05)^{10} = 0.9999999999999$$
This generates a catastrophic false certainty: one single unverified forum post mirrored 10 times appears mathematically indisputable.

### 4.2 Deduplication Protocol
To enforce Edge Case **EC-24**:
1. Ingestion adapters assign an `independence_group_id` based on source origin, content hash, and indicator provenance.
   - For mirrors: `indep_mirror_<content_hash>`
   - For same-profile observations: `indep_profile_<actor_id>_<indicator_type>`
2. During fusion aggregation, evidence is partitioned by `(Category, independence_group_id)`.
3. Within each partition, only the maximum observed weight is admitted to the Noisy-OR product:
   $$w_{\text{effective}}(g) = \max \{ w_u \mid u \in \text{Group}_g \}$$
4. Redundant, mirrored, or repeated scrapes contribute zero incremental score, preventing inflation while preserving the raw evidence records for investigative provenance.

---

## 5. Scoring Caps & Defensive Guardrails

To prevent deceptive or low-assurance signals from creating ungrounded high-confidence links, the engine implements four mandatory caps:

### 5.1 Category S Hard Ceiling ($\le 0.20$)
Semantic similarity (SBERT) and classical stylometry are vulnerable to:
- Topic-driven vocabulary overlap (two different actors discussing ransomware).
- Machine translation smoothing (Russian to English translators normalizing style).
- LLM assistance / generative drafting (ChatGPT-style rephrasing).

Therefore, regardless of how high the cosine similarity or how many stylometric units are ingested, the Category S score is capped at `0.20`. Stylometry can never elevate an actor link into `possible_association` ($0.40$) on its own.

### 5.2 Text-Only & Behavioral-Only Ceiling ($\le 0.65$)
If an actor pair has evidence consisting exclusively of text similarity (Category S) and behavioral patterns (Category B) without any cryptographic ($K=0$) or infrastructure ($I=0$) anchors:
$$Score_{\text{final}} \le 0.65$$
Under no circumstance can text-only evidence reach `likely_same_actor` ($\ge 0.70$) or `observed_technical_identity` ($\ge 0.90$). It is bounded strictly within `possible_association`.

### 5.3 Infrastructure-Alone Ceiling ($\le 0.65$)
Shared SSL certificates, CDN IPs, or shared web servers (Category I) frequently occur due to shared bulletproof hosting providers or default Nginx configurations. Infrastructure matches alone are capped at `0.65` and cannot reach `likely_same_actor` without cryptographic corroboration.

### 5.4 Cryptocurrency Wallet Role Downweighting (EC-09)
Per Edge Case **EC-09**, cryptocurrency wallets are evaluated by `indicator_role`:
- `wallet_unknown`: Default on-chain address $\to$ weight $0.90$.
- `shared_service_wallet`: Known centralized deposit address $\to$ downweighted to $0.20$.
- `mixer_suspected`: Suspected mixer/tumbler pooling address $\to$ downweighted to $0.10$.

---

## 6. Tier Boundaries & Qualitative Semantics

The platform maps continuous fused scores $[0.00, 1.00]$ to five discrete attribution tiers:

```
0.00            0.20            0.40            0.70            0.90          1.00
  ├───────────────┼───────────────┼───────────────┼───────────────┼─────────────┤
  │ Insufficient  │  Unresolved   │   Possible    │  Likely Same  │  Observed   │
  │   Evidence    │               │  Association  │     Actor     │  Technical  │
  │               │               │               │               │  Identity   │
```

| Tier Name | Score Range | Operational Meaning & Actionability |
|---|:---:|---|
| `insufficient_evidence` | $[0.00, 0.20)$ | Minimal or uncorroborated weak signals. Insufficient grounds for investigative action. Retained as background telemetry. |
| `unresolved` | $[0.20, 0.40)$ | Multiple weak or conflicting signals. Requires additional collection before forming a candidate hypothesis. |
| `possible_association` | $[0.40, 0.70)$ | Substantive correlation (e.g. strong infrastructure match or behavioral pattern). Merits analyst tracking, but insufficient for formal attribution. |
| `likely_same_actor` | $[0.70, 0.90)$ | High-confidence correlation supported by multiple independent vectors (e.g. infrastructure + verified alias + behavioral match). Primary candidate for investigative review. |
| `observed_technical_identity` | $[0.90, 1.00]$ | Conclusive technical link anchored by verified cryptographic material (PGP signature, direct private wallet reuse, or cryptographic multi-vector corroboration). |

---

## 7. Boundary Hysteresis Margin (EC-25)

### 7.1 The Problem: Boundary Flicker
In an automated pipeline where evidence is continuously streamed, small fluctuations in weights (e.g., dynamic model score updates, timestamp decay, or minor confidence adjustments) can cause a candidate link near a tier boundary (e.g. $0.699 \leftrightarrow 0.701$) to flip repeatedly between `possible_association` and `likely_same_actor`. This generates alert fatigue and invalidates analyst workflow queues.

### 7.2 The Hysteresis Mechanism
To satisfy **EC-25**, the scoring engine enforces a symmetric deadband hysteresis margin:
$$\Delta_{\text{hysteresis}} = \pm 0.03$$

When re-evaluating an existing candidate link with previous score $Score_{\text{prev}}$ and tier $Tier_{\text{prev}}$:
1. Compute the raw candidate tier $Tier_{\text{raw}}$ from $Score_{\text{new}}$.
2. If $|Score_{\text{new}} - Score_{\text{prev}}| \le 0.03$, the link retains $Tier_{\text{prev}}$.
3. The tier transitions only if the score change strictly exceeds the margin ($|Score_{\text{new}} - Score_{\text{prev}}| > 0.03$).

### 7.3 Hysteresis Transition Matrix Examples

| Previous Score | Previous Tier | New Score | Score $\Delta$ | Raw New Tier | Assigned Tier | Transition Outcome |
|:---:|---|:---:|:---:|---|---|---|
| $0.68$ | `possible_association` | $0.71$ | $+0.03$ | `likely_same_actor` | **`possible_association`** | Boundary transition suppressed (flicker prevented) |
| $0.68$ | `possible_association` | $0.74$ | $+0.06$ | `likely_same_actor` | **`likely_same_actor`** | Upgraded (exceeds margin) |
| $0.72$ | `likely_same_actor` | $0.69$ | $-0.03$ | `possible_association` | **`likely_same_actor`** | Downgrade transition suppressed |
| $0.72$ | `likely_same_actor` | $0.66$ | $-0.06$ | `possible_association` | **`possible_association`** | Downgraded (exceeds margin) |
| $0.39$ | `unresolved` | $0.41$ | $+0.02$ | `possible_association` | **`unresolved`** | Boundary transition suppressed |
| *None* | *(New Link)* | $0.71$ | N/A | `likely_same_actor` | **`likely_same_actor`** | Direct raw mapping on initial evaluation |

---

## 8. Conflict Resolution & Competing Hypotheses (EC-13)

### 8.1 Competing Link Hypotheses
When evaluating threat actors across multiple underground platforms, an actor persona may appear to link to multiple mutually exclusive identities. For example:
- Candidate Link 1: Actor $A$ linked to Actor $B$ (via shared wallet).
- Candidate Link 2: Actor $A$ linked to Actor $C$ (via shared PGP key).
- Context: Actor $B$ and Actor $C$ are established as separate, adversarial personas.

Treating these as independent positive links creates logical contradictions.

### 8.2 Conflict Resolution Algorithm (`ConflictResolver`)
1. **Entity Graph Projection:** Build a bipartite entity participation map:
   $$M(E) = \{ L \in \text{CandidateLinks} \mid E \in \{L.\text{left\_entity}, L.\text{right\_entity}\} \}$$
2. **Conflict Set Identification:** For every link $L$, identify all overlapping links sharing either entity endpoint:
   $$\text{Competing}(L) = (M(L.\text{left\_entity}) \cup M(L.\text{right\_entity})) \setminus \{ L \}$$
3. **Deterministic Conflict Set ID:** If competing links exist, assign a deterministic conflict cluster ID derived from the sorted member link IDs:
   $$\text{conflict\_set\_id} = \text{"conf\_"} + \text{SHA256}\left(\text{sorted}(L_{\text{ids}})\right)[0:12]$$
4. **Link Annotation:** Update each competing link with:
   - `conflict_set_id`: The cluster identifier.
   - `competing_link_ids`: Array of competing link IDs.
   - `score_status`: Set to `"conflicting"`.
5. **Analyst Presentation:** In the analyst dashboard, conflicting links are visually badged with a warning icon and presented side-by-side for comparative review.

---

## 9. CandidateLink Lifecycle State Machine & Versioning

### 9.1 State Machine Specification
Candidate links transition through five strictly validated lifecycle states:

```
                  ┌──────────────┐
                  │   proposed   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
          ┌──────▶│ needs_review │◀─────┐
          │       └──────┬───────┘      │
          │              │              │
          ▼              ▼              ▼
   ┌──────────────┐              ┌──────────────┐
   │   accepted   │◀────────────▶│   rejected   │
   └──────┬───────┘              └──────┬───────┘
          │                             │
          └──────────────┬──────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  superseded  │  (Terminal)
                  └──────────────┘
```

- **`proposed`:** Automatically generated by fusion engine upon score calculation.
- **`needs_review`:** Flagged for triage due to high confidence, boundary proximity, or conflict detection.
- **`accepted`:** Formally confirmed by an authorized intelligence analyst (reversion to `needs_review` or `rejected` permitted).
- **`rejected`:** Discarded by analyst as false positive / coincidental (reversion permitted).
- **`superseded`:** Terminal state. Automatically applied when a new pipeline run ingests newer evidence for the entity pair.

### 9.2 Immutable Versioning Snapshotting
Every transition executed by `LinkLifecycleManager.transition_state()`:
1. Increments `link_version` by 1.
2. Updates `updated_at` with ISO-8601 UTC timestamp.
3. Inserts an immutable row into `candidate_link_versions` capturing:
   - `version_id` (UUID)
   - `link_id`, `link_version`, `state`, `score`, `tier`
   - Complete serialized `category_breakdown_json`, `evidence_ids_json`, `limitations_json`
   - `calculation_input_hash`
   - `changed_by` (analyst ID or system service)
   - `reason` (mandatory rationale)

### 9.3 Calculation Input Hash (`calculation_input_hash`)
For audit reproducibility and idempotency, every calculation produces a deterministic input hash:
$$\text{calculation\_input\_hash} = \text{"sha256:"} + \text{SHA256}\left(\text{model\_version} + \text{":"} + \text{sorted\_evidence\_ids}\right)$$

If an identical set of evidence units is re-evaluated under the same scoring model version, the exact same input hash is generated, triggering idempotent retrieval without creating redundant database records.

---

## 10. Scoring Model Configuration (`config/scoring.yaml`)

All algorithmic constants, category weights, contribution limits, and tier thresholds are governed by `config/scoring.yaml`:

```yaml
score_model_version: "scoring-v1.0"
hysteresis_margin: 0.03

categories:
  K:
    name: "Cryptographic & Hard Identifiers"
    weight: 1.00
    max_contribution: 1.00
  I:
    name: "Infrastructure"
    weight: 0.85
    max_contribution: 0.65
  B:
    name: "Behavioral"
    weight: 0.80
    max_contribution: 0.65
  S:
    name: "Semantic & Stylometric"
    weight: 0.70
    max_contribution: 0.20

tiers:
  insufficient_evidence:
    min_score: 0.00
    max_score: 0.20
  unresolved:
    min_score: 0.20
    max_score: 0.40
  possible_association:
    min_score: 0.40
    max_score: 0.70
  likely_same_actor:
    min_score: 0.70
    max_score: 0.90
  observed_technical_identity:
    min_score: 0.90
    max_score: 1.00
```

Modifications to `scoring.yaml` bump `score_model_version`, which cleanly isolates prior calculations and facilitates audited historical rescoring.
