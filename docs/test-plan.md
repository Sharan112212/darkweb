# SIH26151 — Test Plan

## Test Strategy

All branches must include tests before merge. Tests are organized into three tiers.

### Tier 1: Unit Tests (`tests/unit/`)
- Individual function/class validation
- Pydantic model schema validation (valid + malformed input)
- Adapter output validation
- Normalization rule checks
- Gate/threshold enforcement
- Run time: < 30 seconds total

### Tier 2: Integration Tests (`tests/integration/`)
- End-to-end data path per branch
- Database round-trip (write → read → validate)
- Adapter → fusion → CandidateLink pipeline
- Docker service health checks
- Run time: < 5 minutes total

### Tier 3: API Tests (`tests/api/`)
- REST endpoint request/response validation
- RBAC enforcement across all roles
- Pagination and rate limiting
- Error responses and audit trail creation
- Run time: < 2 minutes total

## Required Test Fixtures (16 scenarios)

| # | Fixture | Tests | Branch |
|---|---|---|---|
| 1 | Shared PGP in two profiles | Identity adapter, K-category scoring | 1 |
| 2 | Text/behavior-only pair | Score cap enforcement (≤ possible_association) | 3 |
| 3 | GhostVendor → Nightshade99 rebrand | Behavior engine, timeline events | 7 |
| 4 | Shared mixer/escrow wallet (negative) | Wallet role downweight, insufficient_evidence tier | 2 |
| 5 | Offline source → 503 → changed | Capture status events, evidence retention | 2 |
| 6 | Mirrored/reposted identical page | independence_group_id dedup | 2 |
| 7 | Oversized/malformed HTML | Quarantine path, metadata preservation | 2 |
| 8 | Published PGP vs verified signature | indicator_role distinction | 1 |
| 9 | Unicode-confusable/recycled alias | Normalization, collision warning | 1 |
| 10 | Competing actor-hypothesis conflict | Conflict set creation | 3 |
| 11 | Translation/code-switching/short corpus | Stylometry gate enforcement | 8 |
| 12 | LLM-like/style imitation | Not-high-tier enforcement | 8 |
| 13 | Stale certificate/header | Freshness decay in scoring | 4 |
| 14 | Concurrent duplicate collection jobs | Idempotency constraint | 2 |
| 15 | Decision/evidence change during export | Snapshot integrity | 9 |
| 16 | Redaction and unauthorized export | RBAC enforcement | 9 |

## Edge Case Test Mapping

Every P0 edge case (from Edge Case Register) must have at least one automated test before the branch that owns it can merge.

## Test Commands

```bash
# Run all tests
make test

# Run specific tier
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/api/ -v

# Run specific branch tests
python -m pytest tests/integration/test_branch2_e2e.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Lint + security
make lint
```

## CI/CD Pipeline (Target)

1. Lint (flake8 + bandit)
2. Secret scan
3. Unit tests
4. Integration tests (requires Docker)
5. API tests
6. Dependency/license check
7. SBOM generation
