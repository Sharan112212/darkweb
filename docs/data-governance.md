# SIH26151 — Data Governance, Audit, and Export Policy

## 1. Overview
This document specifies the data governance, audit logging, role-based access control (RBAC), data redaction, legal hold, and export snapshot policies for the SIH26151 Dark-Web Threat Actor Attribution Platform.

## 2. Role-Based Access Control (RBAC) Policy

| Role | Search & Profiles | Evidence Drawer | Link Decisions | Export Reports | Admin & Audit Log |
|---|---|---|---|---|---|
| **Viewer** | Full access | Redacted (Masked keys/excerpts) | Blocked | Blocked | Blocked |
| **Analyst** | Full access | Full evidence details | Create decisions (with note) | Export JSON/CSV/PDF | Read audit log |
| **Reviewer** | Full access | Full evidence details | Approve/revert decisions | Export JSON/CSV/PDF | Legal hold control |
| **Admin** | Full access | Full evidence details | Full access | Export JSON/CSV/PDF | Full admin & system log |

## 3. Tamper-Evident Audit Strategy (EC-27)
- **Hash-Chained Audit Trail:** Every audit event includes `previous_event_hash` and `event_hash`:
  $$\text{event\_hash} = \text{SHA256}(\text{prev\_hash} \mid \text{event\_id} \mid \text{request\_id} \mid \text{user\_id} \mid \text{action} \mid \text{object\_id} \mid \text{timestamp} \mid \text{details\_json})$$
- **Append-Only Enforcement:** Attempts to edit or delete existing audit logs break the cryptographic hash chain and trigger an immediate integrity alert.
- **Verification API:** `GET /api/v1/audit` executes dynamic hash chain verification across all records.

## 4. Export Snapshot & Version Locking (EC-35)
- **Freeze Before Render:** Export snapshots freeze exact versions of evidence units, candidate links, actors, score model version (`scoring-v1.0`), and calculation input hashes.
- **Immutability:** Subsequent modifications to database records do NOT alter pre-generated export snapshots.
- **Mandatory Disclaimer:** All exported reports (JSON, CSV, PDF) contain the mandatory analyst disclaimer:
  > *"This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation."*

## 5. Data Redaction & Tombstoning (EC-28, EC-36)
- **Viewer Redaction:** Sensitive indicators (PGP keys, contact identifiers, raw HTML excerpts) are masked for `viewer` role with explicit notices.
- **Legal Hold:** Setting `legal_hold = true` on a case or entity blocks all retention deletion and tombstoning operations.
- **Tombstone Policy:** Expiry or takedown of evidence replaces payload content with a tombstone record while retaining original audit trails.
