import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Investigation } from "./Investigation";
import { GraphView } from "./GraphView";
import { Timeline } from "./Timeline";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { Ic } from "./icons";
import { Link } from "./data";
import { BackendStatus, getToken, ping } from "./api";

type View = "investigation" | "graph" | "timeline" | "cases";

const NAV: [View, string, JSX.Element][] = [
  ["investigation", "Investigation", Ic.invest],
  ["graph", "Attribution graph", Ic.graph],
  ["timeline", "Timeline", Ic.time],
  ["cases", "Cases & export", Ic.cases],
];

export default function App() {
  const [view, setView] = useState<View>("investigation");
  const [role, setRole] = useState("analyst");
  const [plain, setPlain] = useState(true);
  const [drawer, setDrawer] = useState<Link | null>(null);
  const [status, setStatus] = useState<BackendStatus>("checking");

  // Prove live connectivity + RBAC against the FastAPI (falls back to demo).
  useEffect(() => {
    let alive = true;
    (async () => {
      const ok = await ping();
      if (!alive) return;
      if (!ok) return setStatus("demo");
      await getToken("demo_user", role);
      if (alive) setStatus("live");
    })();
    return () => { alive = false; };
  }, []); // eslint-disable-line

  const statusLabel = status === "live" ? "Live API connected" : status === "demo" ? "Demo data (API offline)" : "Checking API…";

  return (
    <div className="app">
      <nav className="rail">
        <div className="glyph">T</div>
        {NAV.map(([k, label, ic]) => (
          <button key={k} className={"navbtn" + (view === k ? " on" : "")} onClick={() => setView(k)} aria-label={label}>
            {ic}<span className="tip">{label}</span>
          </button>
        ))}
      </nav>

      <div className="main">
        <header className="top">
          <div className="brand"><b>Throughline</b><small>Evidence-first attribution</small></div>
          <div className="spacer" />
          <div className="statuspill" title={statusLabel}><span className={"d " + status} />{statusLabel}</div>
          <div className="toggle" onClick={() => setPlain((p) => !p)} role="switch" aria-checked={plain}>
            Plain English<div className={"sw" + (plain ? " on" : "")}><i /></div>
          </div>
          <div className="role">
            <span className="dot" />
            <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role">
              <option value="viewer">Viewer</option>
              <option value="analyst">Analyst</option>
              <option value="reviewer">Reviewer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </header>

        <div className="ribbon">
          {Ic.warn}
          <div><b>Disclosure.</b> Confidence-scored <b style={{ color: "var(--ink)" }}>technical</b> associations for authorized analyst review. It does not defeat Tor, establish a real-world identity, or replace legal investigation.</div>
        </div>

        <div className="canvas">
          {view === "investigation" && <Investigation plain={plain} onOpen={setDrawer} />}
          {view === "graph" && <GraphView onOpen={setDrawer} />}
          {view === "timeline" && <Timeline />}
          {view === "cases" && (
            <div className="verdict">
              <div className="eyebrow">Cases &amp; export</div>
              <h2>Freeze the evidence, export the report</h2>
              <p>An export snapshots the exact evidence IDs, link versions and model version at that instant — so a later change never alters an already-issued report. Every export carries the disclosure and a SHA-256 fingerprint.</p>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {drawer && <EvidenceDrawer key={drawer.id} link={drawer} plain={plain} onClose={() => setDrawer(null)} />}
      </AnimatePresence>
    </div>
  );
}
