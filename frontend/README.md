# Throughline — Frontend

A modern, jury-facing UI for the SIH26151 attribution platform. It is **fully
isolated** from the existing Python system — it lives only in this `frontend/`
folder, changes **no** backend code, and talks to the FastAPI over HTTP.

## Run it

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

That's all you need for the demo — the app ships with the demo scenarios
(the same cases the pipeline produces: DarkFox rebrand, ViperX multi-signal,
the text-only cap, and the rejected mixer-wallet false positive), so it always
renders, even with no backend running.

## Connect it to the live API (optional)

In a second terminal, from the repo root:

```bash
python -m uvicorn api.app:app --reload --port 8000
```

The Vite dev server proxies `/api/*` → `http://localhost:8000` (see
`vite.config.ts`), so there are no CORS issues and nothing to configure. The
status pill in the header turns **green ("Live API connected")** once it reaches
`/api/v1/health` and successfully mints a JWT — proving the real backend + RBAC
are wired up.

The rich attribution scenarios stay on the bundled fixtures for a dependable
demo. To drive a view entirely from live data once the canonical DB is
populated, the helpers in `src/api.ts` (`liveActor`, `liveGraph`) already call
`GET /api/v1/actors/{id}` and `GET /api/v1/graph/projection`.

## What's inside

| File | Screen |
|---|---|
| `src/Investigation.tsx` | Actor profile + verdict banner + linked-persona cards |
| `src/EvidenceDrawer.tsx` | The evidence chain (source → indicator → … → limitation) |
| `src/GraphView.tsx` | Animated attribution graph (edge = tier, thickness = confidence) |
| `src/Timeline.tsx` | Investigation timeline with ⚠ approximate markers |
| `src/data.ts` | Demo fixtures + tier system (single source of truth) |
| `src/api.ts` | Live-backend probe + JWT + optional live-data helpers |

## Build for production

```bash
npm run build      # outputs to dist/
npm run preview    # serve the built bundle
```

## Stack
React 18 · TypeScript · Vite · Framer Motion. No backend changes; Streamlit and
the Python pipeline are untouched and remain the fallback demo path.
