# SIH26151 — Air-Gapped Local Demo Runbook

This document provides step-by-step instructions for deploying and running the **SIH26151 Dark-Web Threat Actor Attribution Platform** in an isolated, air-gapped environment (e.g., presentation booth or offline evaluation station).

---

## 1. Environment & Offline Prerequisites

The platform is designed to operate **100% offline with zero internet access** (`EC-37`).

### Pre-Bundled Components
- **Model Weights:** Pre-cached Sentence-BERT model (`models/all-MiniLM-L6-v2/`) bundled directly in the workspace.
- **Fixtures:** 16 offline synthetic fixtures (`fixtures/`) with SHA-256 manifest verification (`fixtures/manifests/fixture_manifest.json`).
- **Dependencies:** All Python packages and Docker images pre-cached.

---

## 2. Quick Deployment (3 Steps)

### Step 1: Environment Setup
Copy the environment template (if `.env` does not exist):
```bash
cp .env.example .env
```

### Step 2: Reset Demo State
Reset database schema, seed synthetic entities, and clear previous runs:
```bash
make demo-reset
```
*Alternatively, run Python script directly:*
```bash
python db_setup.py
python run_pipeline.py
```

### Step 3: Launch Platform
Start the FastAPI backend server and Streamlit dashboard:
```bash
# Production Docker stack:
make up

# Or local development mode:
uvicorn api.app:app --host 0.0.0.0 --port 8000 &
streamlit run dashboard.py --server.port 8501
```

---

## 3. Verifying System Health

1. **API Health Check:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
   *Expected Response:* `{"status": "healthy", "mode": "fixture_replay"}`

2. **Dashboard UI:**
   Open browser to `http://localhost:8501`.

3. **Audit Log Integrity Verification:**
   ```bash
   python -c "from governance.audit import AuditStore; print(AuditStore().verify_integrity())"
   ```
   *Expected Response:* `{"valid": true, "events_checked": ...}`

---

## 4. Troubleshooting & Offline Fallbacks

- **Neo4j Offline:** The system automatically falls back to in-memory NetworkX graph projection (`EC-07`). No user action required.
- **OnionScan Binary Offline:** The scanner automatically replays fixture outputs (`fixtures/onionscan/`).
- **Emergency Clean Reset:** `make down && make demo-reset && make up`
