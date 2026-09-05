import { motion } from "framer-motion";
import { TIERS, TL } from "./data";
import { Ic } from "./icons";

export function Timeline() {
  return (
    <div>
      <div className="verdict" style={{ marginBottom: 18, ["--tc" as any]: "var(--accent)" }}>
        <div className="rail3" style={{ background: "var(--accent)" }} />
        <div className="eyebrow">Investigation timeline</div>
        <h2>The story over time</h2>
        <p>
          Events use the real recorded time where we have it. When a date is only <em>claimed</em> by the source and can't be
          trusted, it is marked <span style={{ color: "var(--amber)" }}>⚠ approximate</span> — never shown as fact.
        </p>
      </div>
      <div className="tlwrap">
        {TL.map((e, i) => (
          <motion.div
            className="tl"
            key={i}
            style={{ ["--tc" as any]: `var(${TIERS[e.tier].v})` }}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08, duration: 0.4 }}
          >
            <div className="when">{e.when}{e.approx && <span className="ap">⚠ approximate</span>}</div>
            <div className="mark"><div className="dot" /></div>
            <div className={"body" + (e.approx ? " approx" : "")}><b>{e.title}</b><div className="d">{e.d}</div></div>
          </motion.div>
        ))}
      </div>
      <div className="foot">{Ic.time}<div>Dates are shown in <b style={{ color: "var(--ink)" }}>UTC</b>. The same date filter drives both this timeline and the graph, so the two never disagree.</div></div>
    </div>
  );
}
