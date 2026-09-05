# SIH26151 — 5-Minute Live Jury Presentation Script

**Project Title:** Evidence-First Dark-Web Threat Actor Attribution Platform  
**Target Duration:** 5 Minutes (4 Key Scenarios)

---

## Mandatory System Disclosure Statement
*(Displayed on Dashboard Banner and Report Headers per Build Guide §19)*

> **"This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation."**

---

## Scenario 1: Easy Case — High-Confidence Cryptographic Link (1.5 Mins)

**Objective:** Demonstrate search, identity correlation, Evidence Drawer, and probabilistic scoring.

1. **Action:** On the Streamlit Dashboard (`http://localhost:8501`), search for entity `GhostVendor`.
2. **Observe:** 
   - Entity summary panel displays associated personas and candidate links.
   - High-confidence link found with score **0.95** (Tier: `observed_technical_identity`).
3. **Click Link / Edge:** Open the **Evidence Drawer**.
4. **Analyst Narrative:**
   > *"Notice that we do not present a black-box score. When we click on the link, the Evidence Drawer opens to show the exact evidence chain: a matching 40-character PGP fingerprint verified across marketplace profiles (`K` category), paired with an associated Bitcoin wallet. Every piece of evidence lists its observation date, SHA-256 capture hash, and explicit caveats — such as 'Published key is not proof of key control'."*

---

## Scenario 2: Rebrand Case — Persona Migration & Timeline Analysis (1 Min)

**Objective:** Demonstrate cross-market persona tracking across time without identity loss.

1. **Action:** Navigate to the **Timeline Explorer** tab for `GhostVendor`.
2. **Observe:**
   - Chronological event progression: `GhostVendor` active on Market-A → Account Inactive → `Nightshade99` created on Market-A with identical stylometric signature and posting time profile → Rebrand event generated.
3. **Analyst Narrative:**
   > *"Threat actors frequently exit-scam or retire handles to evade law enforcement. Our Timeline Engine correlates posting schedules, vocabulary overlaps, and infrastructure overlap to trace handle shifts. Here we see GhostVendor transitioning to Nightshade99 while preserving the historical evidence chain without destructive entity merging."*

---

## Scenario 3: Hard Case — Text-Only Similarity Cap (1 Min)

**Objective:** Demonstrate strict evidence caps preventing text similarity from claiming identity.

1. **Action:** Select candidate pair `VendorAlpha` vs `VendorBeta` (linked only by MiniLM semantic similarity and classical stylometry).
2. **Observe:**
   - Fusion score: **0.20** (Tier: `possible_association`).
   - Warning badge: `Capped: Text & Stylometry signals alone cannot exceed possible_association tier`.
3. **Analyst Narrative:**
   > *"A critical safety requirement of our platform is enforcing scientific evidence boundaries. Even when two actors write with very similar style, text-only evidence is capped at a max contribution of 0.20. It can NEVER reach 'likely_same_actor' without corroborating cryptographic or infrastructure proof."*

---

## Scenario 4: Negative Case — Shared Escrow/Mixer Wallet Downweighting (1.5 Mins)

**Objective:** Demonstrate false-positive prevention on shared infrastructure/services.

1. **Action:** Inspect entity pair sharing a known darknet mixer/escrow wallet (`1SharedMixerWalletAddr...`).
2. **Observe:**
   - Score: **0.10** (Tier: `insufficient_evidence`).
   - Category Breakdown: Wallet role tagged as `shared_service_wallet / mixer_suspected`.
   - Limitation String: `["Shared service wallet detected; downweighted to prevent false positive link"]`.
3. **Analyst Narrative:**
   > *"Naive correlation engines generate massive false positives when two unrelated actors use the same darkweb escrow or coin mixer. Our system automatically recognizes shared service wallets, applies downweighting, and flags the pair as 'insufficient evidence' — ensuring law enforcement resources are never wasted on false leads."*
