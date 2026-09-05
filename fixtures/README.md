# SIH26151 — Threat Actor Attribution Platform: Test Fixture Library

This directory contains the canonical synthetic test fixtures for the SIH26151 Dark-Web Threat Actor Attribution Platform. The fixtures provide deterministic, offline-capable test data for evaluating data collection, stylometric analysis, cryptographic identity graphs, infrastructure matching, and multi-signal probabilistic fusion without touching real dark web services.

---

## 1. Synthetic Fixture Policy

To strictly adhere to legal, operational, and ethical guidelines (specifically **EC-40** in the system risk register), the platform enforces a zero-live-content policy:

- **100% Synthetic Content**: No data in this repository originated from live dark web marketplaces, forums, or threat actors. All usernames, PGP keys, Bitcoin wallets, listing titles, and forum posts are procedurally generated synthetic mock data.
- **Mock URIs and Schemas**: Fixtures are accessed via the `fixture://` URI scheme (e.g., `fixture://market-a/ghostvendor.html`). No real `.onion` addresses or live clearnet IPs are referenced.
- **Passive Replay Safety**: Collectors operating against these fixtures simulate SOCKS5h Tor collection and capture lifecycle events without performing active exploitation, JavaScript execution, or anti-bot bypass.
- **Determinism and Reproducibility**: All fixture files are pinned with deterministic UNIX line endings (`\n`) and SHA-256 checksums, enabling byte-for-byte reproducibility across all test environments and CI pipelines.

---

## 2. Directory Structure and Fixture Catalog

```
e:\darkwebsih\fixtures\
├── README.md                          # Documentation of fixture library and policies
├── manifests/
│   └── fixture_manifest.json          # SHA-256 checksums and file size manifest
├── market-a/
│   ├── ghostvendor.html               # Baseline vendor profile (inactive, arms/security tools)
│   ├── nightshade99.html              # Rebrand target profile (active, matching stylometry)
│   ├── ghostvendor_offline.html       # EC-01 simulation: 503 Service Unavailable outage
│   └── ghostvendor_changed.html       # EC-01 simulation: Updated profile content upon recovery
├── market-b/
│   ├── mirror_ghostvendor.html        # EC-02 simulation: Cross-market mirror / repost deduplication
│   ├── mixer_pair_a.html              # EC-09 negative control: Actor alpha sharing mixer wallet
│   ├── mixer_pair_b.html              # EC-09 negative control: Actor beta sharing mixer wallet
│   └── oversized.html                 # EC-03 simulation: >10MB payload for quarantine pipeline
└── blocked/
    └── captcha_page.html              # EC-04 simulation: CAPTCHA / login required source
```

---

## 3. Fixture Details and Edge Case Mappings

### `market-a/ghostvendor.html` — Baseline Profile
- **Actor Handle**: `GhostVendor`
- **Status**: `Inactive` (Category: `Arms & Hardware`, Last Seen: `2026-05-14`)
- **Cryptographic PGP Fingerprint**: `1122 33AA BBCC DD44 5566  7788 99EE FF00 1234 5678`
- **Cryptocurrency Wallet**: `3GhostVendorFakeWallet000000000000`
- **Stylometric Signatures**: Distinct colloquial phrases including `"yo fam"`, `"quality checked twice"`, and `"definately worth the wait"`.
- **Purpose**: Serves as the primary source actor for rebrand detection and lifecycle transition tracking.

### `market-a/nightshade99.html` — Rebrand Target Profile
- **Actor Handle**: `Nightshade99`
- **Status**: `Active` (Category: `Arms & Hardware`, Last Seen: `2026-08-01`)
- **Cryptographic PGP Fingerprint**: `AABB CCDD 0099 8877 6655  4433 2211 0FED CBA9 8765` (Completely distinct)
- **Cryptocurrency Wallet**: `1NightshadeFakeWallet000000000000` (Completely distinct)
- **Stylometric Signatures**: Exact stylistic match with `GhostVendor` (`"yo fam"`, `"quality checked twice"`, `"definately worth the wait"`).
- **Purpose**: Validates Sentence-BERT stylometry extraction in the absence of shared cryptographic or financial indicators.

### `market-a/ghostvendor_offline.html` — EC-01: Source Offline Outage
- **Simulated Response**: HTTP 503 Service Temporarily Unavailable.
- **Content**: Error notice stating maintenance and server outage.
- **Expected System Behavior**: The collector records a `Capture` record with `status="failed"`, `http_status=503`, and preserves existing historical observations without deleting or invalidating prior intelligence.

### `market-a/ghostvendor_changed.html` — EC-01: Content Change on Recovery
- **Simulated Response**: HTTP 200 OK after source returns online.
- **Content**: Status changed to `Retired`, category changed to `Archive`, and notice updated to indicate account closure.
- **Expected System Behavior**: The collector records a new capture with a different SHA-256 hash (`f7024cc6...` vs `023e0432...`), triggering a change detection event in the audit trail.

### `market-b/mirror_ghostvendor.html` — EC-02: Mirror / Repost Deduplication
- **Actor Profile**: Mirror of `GhostVendor` hosted on Market B.
- **Identifiers**: Same PGP key (`1122 33AA...`) and Bitcoin wallet (`3GhostVendor...`).
- **Expected System Behavior**: The pipeline detects mirrored/reposted data and assigns a common `independence_group_id`. This prevents the Noisy-OR fusion engine from erroneously treating mirror observations as independent corroboration (preventing score inflation per EC-24).

### `market-b/oversized.html` — EC-03: Quarantine Path for Oversized Content
- **File Size**: > 10MB (10,486,863 bytes of padded HTML markup).
- **Expected System Behavior**: `CollectionNormalizer` detects that the payload exceeds the 10MB safety threshold, marks the record as `quarantined`, strips execution paths, and preserves raw metadata (`size_bytes`, `sha256`) in audit logs without crashing backend memory.

### `market-b/mixer_pair_a.html` & `market-b/mixer_pair_b.html` — EC-09: Negative Control Pair
- **Actors**: `mixer_user_alpha` (business inquiries) and `mixer_user_beta` (technical solder tutorials).
- **Shared Indicator**: Solely the known tumbler/mixer wallet address `1SharedMixerWalletAddr0000000000000`.
- **Expected System Behavior**: Because the shared indicator is classified as a mixer/escrow service, the identity engine downweights its evidence role, scoring the pair strictly as `insufficient_evidence` and preventing false-positive attribution.

### `blocked/captcha_page.html` — EC-04: Passive Anti-Bot Handling
- **Content**: HTML form containing CAPTCHA challenge elements (`<form id="captcha-form">`, `<div class="g-recaptcha">`).
- **Expected System Behavior**: Collector passively detects the CAPTCHA barrier, records `status="blocked"` with `not_collected_reason="Source requires CAPTCHA / authentication — no bypass attempted"`, and halts without attempting automated solver bypass.

---

## 4. SHA-256 Manifest Validation

All fixture files must strictly match the SHA-256 digests and file sizes cataloged in `manifests/fixture_manifest.json`. Any unintended modification or line-ending divergence will cause integrity validation to fail.

### Manifest File Format (`manifests/fixture_manifest.json`)
```json
{
  "blocked/captcha_page.html": {
    "sha256": "37c141076273b0cefe52c786b3d83ece20b454d437151b22bb5a20655ff3dad4",
    "size_bytes": 579
  },
  "market-a/ghostvendor.html": {
    "sha256": "023e04327231c77324cd208392f7dc22a823a4f031c64bb6dc658c36df9710a8",
    "size_bytes": 1163
  }
}
```

### Manifest Verification Command
To verify the integrity of all test fixtures against the manifest, execute the following command from the project root:

```bash
python -c "
import os, json, hashlib

fixtures_dir = 'fixtures'
manifest_path = os.path.join(fixtures_dir, 'manifests', 'fixture_manifest.json')
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

for rel_path, meta in manifest.items():
    full_path = os.path.join(fixtures_dir, rel_path.replace('/', os.sep))
    assert os.path.exists(full_path), f'Missing fixture: {rel_path}'
    with open(full_path, 'rb') as f:
        data = f.read()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == meta['sha256'], f'Hash mismatch for {rel_path}: {digest} != {meta[\"sha256\"]}'
    assert len(data) == meta['size_bytes'], f'Size mismatch for {rel_path}: {len(data)} != {meta[\"size_bytes\"]}'

print('All fixtures verified successfully against SHA-256 manifest.')
"
```
