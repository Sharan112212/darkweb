# SIH26151 — Test Fixture Library

This directory contains synthetic test fixtures used for offline demo replay, unit testing, and edge-case validation.

## Synthetic Fixture Policy
- **No live content**: All HTML pages, posts, usernames, PGP keys, and wallet addresses are synthetic test data.
- **No real .onion addresses**: All source references use `fixture://` schemes or synthetic domain placeholders.
- **SHA-256 Verification**: All fixtures are cataloged with SHA-256 hashes in `manifests/fixture_manifest.json`.

## Directory Structure

- `market-a/ghostvendor.html` — Easy case: shared PGP fingerprint persona.
- `market-a/nightshade99.html` — Rebrand case: Nightshade99 profile (matching writing style, different key/wallet).
- `market-a/ghostvendor_offline.html` — EC-01: Source unavailable / 503 HTTP status.
- `market-a/ghostvendor_changed.html` — EC-01: Content updated after returning online.
- `market-b/mirror_ghostvendor.html` — EC-02: Mirror / repost page (identical content, testing `independence_group_id`).
- `market-b/oversized.html` — EC-03: Malformed / oversized payload (>10MB) for quarantine testing.
- `market-b/mixer_pair_a.html` & `mixer_pair_b.html` — EC-09: Negative case: Shared mixer wallet between unrelated actors.
- `blocked/captcha_page.html` — EC-04: CAPTCHA / login required source (records `not_collected_reason`).
- `manifests/fixture_manifest.json` — Manifest cataloging exact SHA-256 checksums for all fixtures.
