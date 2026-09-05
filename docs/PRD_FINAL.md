# SIH26151 — Final Product Requirements Document (PRD)

## 1. Product Mission & Boundaries

### Mission
Build an analyst-operated platform that correlates authorized dark-web and related technical observations into candidate actor associations. The system reveals technical overlap between aliases, keys, wallets, services, infrastructure, and writing patterns.

### Mandatory Disclosure (Visible in Dashboard & Reports)
> This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation. Confidence weights are configurable prototype methodology, not a validated intelligence standard.

### Boundaries
- **Allowed:** Synthetic fixtures, allowlisted authorized sources, passive collection via Tor SOCKS5h proxy, metadata & text observation, analyst review.
- **Prohibited:** Exploiting sites, submitting forms, logging in, bypassing CAPTCHA/access controls, interacting with marketplaces, active de-anonymization, claiming natural person identity.

---

## 2. User Roles & Permissions (RBAC)

| Role | Search Redacted | View Evidence | Create Cases | Analyst Decision | Source Config | Admin Audit |
|---|---|---|---|---|---|---|
| **Viewer** | Yes | Redacted only | No | No | No | No |
| **Analyst** | Yes | Full (allowed) | Yes | Yes (with note) | No | No |
| **Reviewer** | Yes | Full | Yes | Yes (high-tier) | No | No |
| **Admin** | Yes | Full | Yes | Yes | Yes | Yes |

---

## 3. Core Capability Requirements

1. **Search & Discovery:** Query handles, PGP fingerprints, wallets, contacts, onion hostnames, domains. Redacted excerpts returned for unauthorized roles.
2. **Canonical Evidence Chain:** Every displayed edge must link to exact `EvidenceUnit` records with source, date, confidence breakdown, and limitations.
3. **Graph Explorer:** Multi-hop time-bounded graph traversal with progressive expansion, node/edge limits, and tier-based edge styling.
4. **Analyst Review & Lifecycle:** Link state machine (`proposed` → `needs_review` → `accepted` | `rejected` | `superseded`). Reversible decisions with mandatory analyst notes.
5. **Persona Migration Detection:** Detect rebranding leads (`GhostVendor` → `Nightshade99`) via multi-signal behavioral and temporal patterns.
6. **Case & Report Snapshot:** Case export captures immutable snapshot manifests of exact evidence IDs, link versions, and model versions.
7. **Offline Demo Mode:** Full platform functionality operable offline using synthetic fixtures and bundled assets.

---

## 4. Key Performance & Operational Indicators

- **Deduplication:** Repeated observations grouped via `independence_group_id` without confidence score inflation.
- **Score Stability:** Hysteresis margin (±0.03) near tier boundaries prevents score fluctuation flicker.
- **Audit Integrity:** Append-only tamper-evident audit logging for all decision, export, and configuration actions.
