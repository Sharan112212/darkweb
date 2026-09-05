# Software Bill of Materials (SBOM) — external artifacts

Tracks third-party executables/containers pinned into the platform, per EC-31
(compromised-dependency mitigation: pin by digest, record provenance).

| Component | Type | Version | Pin (digest) | Source | Used by | Notes |
|---|---|---|---|---|---|---|
| OnionScan (`nao1215/onionscan`) | container image | `1.0.0` | `sha256:<TO BE PINNED>` | https://github.com/nao1215/onionscan (Docker Hub `nao1215/onionscan`) | `scanners/onionscan_runner.py`, `docker-compose.yml` (`onionscan` service, profile `scan`) | Isolated, non-root, internal-only network (Tor SOCKS only), CPU/mem capped. **Not forked/modified.** No live scanning by default. |

## Pinning procedure (EC-31)

Before any live/production scanning, replace the version tag with an immutable digest:

```bash
docker pull nao1215/onionscan:1.0.0
docker inspect --format='{{index .RepoDigests 0}}' nao1215/onionscan:1.0.0
# -> nao1215/onionscan@sha256:<digest>
```

Record the `<digest>` in the table above and switch `docker-compose.yml` from the
`:1.0.0` tag to `nao1215/onionscan@sha256:<digest>`. The runner additionally stores
a SHA-256 of every raw scan output (`artifacts/onionscan/`) so scan provenance is
independently verifiable.
