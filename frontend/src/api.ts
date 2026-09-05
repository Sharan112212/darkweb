// Thin client for the SIH26151 FastAPI. Proxied through Vite (/api -> :8000),
// so no CORS config and no backend changes are needed.
//
// Design choice for a dependable demo: the app renders the bundled demo
// scenarios (data.ts) — which mirror what the real pipeline produces — while
// this client proves LIVE connectivity + RBAC against the running API. When the
// canonical DB is populated you can swap any view to the live endpoints below.

const BASE = "/api/v1";

export type BackendStatus = "checking" | "live" | "demo";

export async function ping(timeoutMs = 1500): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const r = await fetch(`${BASE}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    return r.ok;
  } catch {
    return false;
  }
}

export interface TokenResp { access_token: string; role: string; user_id: string; }

export async function getToken(username: string, role: string): Promise<TokenResp | null> {
  try {
    const r = await fetch(`${BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, role }),
    });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

// --- Optional live-data helpers (used once the canonical DB is populated) ---

export async function liveActor(token: string, actorId: string): Promise<any | null> {
  try {
    const r = await fetch(`${BASE}/actors/${encodeURIComponent(actorId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export async function liveGraph(token: string, minScore = 0): Promise<any | null> {
  try {
    const r = await fetch(`${BASE}/graph/projection?min_score=${minScore}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}
