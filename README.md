# Mock Dark Web Lab — PS 26151 Prototype

A self-contained, self-hosted lab that gives your PS 26151 prototype something
real to scrape, correlate, and analyze — without touching any real dark web
infrastructure. Everything here is synthetic: fake personas, fake posts, fake
"vulnerable" infrastructure that you own and control end to end.

## What's in here

```
darkweb-lab/
├── docker-compose.yml       # orchestrates the whole lab
├── tor/                     # Tor daemon publishing 2 onion services
├── nginx-hidden/            # "vulnerable" hidden service (planted misconfigs)
├── nginx-clearnet/          # its clearnet twin (shares the SSL cert — the leak)
├── certs/                   # shared cert generation script
├── marketplace/             # Flask app serving synthetic personas/posts
├── sample_data/             # personas.json + posts.json (the seed data)
├── scraper/                 # Tor-aware scraper -> writes to SQLite
└── infra-matcher/           # SSL-cert correlation module
```

## What each piece demonstrates (mapped to the PRD)

| PRD capability | What proves it here |
|---|---|
| G1: Infra misconfig detection | `infra-matcher/match_infra.py` proves the hidden service's cert matches the clearnet twin's cert |
| G2: Cross-marketplace identity graph | `DarkFox` / `DarkFox_v2` in `personas.json` share a PGP fingerprint + wallet — your graph module should auto-link them |
| G3: Stylometric persona linking | `GhostVendor` / `Nightshade99` share **no** identifiers but have matching writing style in `posts.json` — only your stylometry module should catch this one |
| Collection | `scraper/scraper.py` does a real crawl over Tor, not manual data entry |

## Prerequisites

- Docker + Docker Compose installed locally
- `openssl` installed locally (for cert generation)
- Python 3.10+ locally (for running the scraper/matcher outside Docker)

## Step-by-step: bring the lab up

### 1. Generate the shared certificate (do this first)
```bash
chmod +x certs/generate_certs.sh
./certs/generate_certs.sh
```
This creates `certs/shared_cert.pem` and `certs/shared_key.pem`. Note the
fingerprint it prints — that's the value your infra-matcher will confirm
matches on both ends.

### 2. Build and start everything
```bash
docker compose up --build -d
```
This starts: `nginx-hidden`, `nginx-clearnet`, `marketplace`, and `tor`
(which publishes the first two — wait, `nginx-clearnet` is intentionally
**not** published over Tor, since it's meant to represent a real public
website, not a hidden service).

### 3. Get your onion addresses
```bash
docker exec -it tor-daemon cat /var/lib/tor/hidden_service_marketplace/hostname
docker exec -it tor-daemon cat /var/lib/tor/hidden_service_vulnerable/hostname
```
Tor can take 30-60 seconds after startup to finish publishing the hidden
services — if these files don't exist yet, wait and retry.

### 4. Verify manually (optional but recommended before recording)
Install Tor Browser or use `torify curl` to visit the marketplace onion
address and confirm you see the persona directory page.

### 5. Run the scraper
```bash
cd scraper
pip install -r requirements.txt
python scraper.py --onion <marketplace-onion-address>.onion
```
This populates `darkweb_intel.db` (SQLite) with real scraped data — this
is the file your identity-graph and stylometry modules should read from.

### 6. Run the infra matcher
```bash
cd ../infra-matcher
pip install -r ../scraper/requirements.txt   # reuses requests[socks]
python match_infra.py --onion <vulnerable-service-onion-address>.onion
```
Expected output: a `[MATCH]` result linking the hidden service to
"TechCorp Cloud Solutions" — this is your G1 capability, live and working.

## Feeding this into the rest of your pipeline

- **Identity graph module**: query `darkweb_intel.db`'s `actors` table,
  group by `pgp_fingerprint` and `wallet_address` — `DarkFox`/`DarkFox_v2`
  should land in the same group automatically.
- **Stylometry module**: pull all rows from `posts` grouped by `handle`,
  run your embedding/similarity comparison across handles — the
  `GhostVendor`/`Nightshade99` pair should score highest despite having
  zero shared identifiers.
- **Dashboard**: point your Streamlit/FastAPI app at `darkweb_intel.db`
  directly for the demo.

## Extending the dataset

`sample_data/personas.json` and `sample_data/posts.json` are plain JSON —
add more personas/posts in the same shape to make the demo richer. Keep
each persona's writing style internally consistent (same slang, same
punctuation habits, same sign-offs) so your stylometry module has a real
signal to detect, not noise.

## Why this approach (for your video's opening/closing narration)

> "For this demo we built a self-contained lab simulating dark web
> infrastructure and marketplace activity, with deliberately planted
> misconfigurations and synthetic actor personas — including a rebrand
> case with shared identifiers and a harder rebrand case with none. Our
> scraper collects this data live over the real Tor network, and our
> analysis pipeline runs on that collected data, not hardcoded values.
> In production, this same pipeline would point at authorized OSINT
> sources instead of our lab environment."

This is accurate, defensible, and directly answers the "is this real"
question before anyone has to ask it.

## Safety notes

- Nothing in this lab reaches outside your own machine/network.
- `nginx-clearnet` is exposed on `localhost:8443` only — not the public
  internet — unless you deliberately choose to deploy it further.
- Do not point the scraper or matcher at any real .onion address or real
  clearnet infrastructure you don't own. This lab is for demonstrating
  the *mechanism*, not for scanning real targets.
