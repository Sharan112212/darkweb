import { useEffect } from "react";
import { motion } from "framer-motion";
import { Link, TIERS } from "./data";
import { Ic } from "./icons";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function EvidenceDrawer({ link, plain, onClose }: { link: Link; plain: boolean; onClose: () => void }) {
  const t = TIERS[link.tier];
  const tc = `var(${t.v})`;
  const c = link.chain;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const steps: [string, string, string?][] = [
    ["Source module", c.source],
    ["Indicator observed", plain ? cap(c.indicatorPlain) : c.indicator, plain ? undefined : c.value],
    ["Who it links", `${link.a}  ⇄  ${link.b}`],
    ["When", c.when],
    ["Reliability", c.reliability],
    ["Confidence contribution", c.contribution],
  ];

  return (
    <>
      <motion.div className="scrim" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
      <motion.aside
        className="drawer"
        style={{ ["--tc" as any]: tc }}
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}
      >
        <div className="dhead">
          <button className="x" onClick={onClose} aria-label="Close">{Ic.x}</button>
          <div className="eyebrow" style={{ color: tc }}>{t.label} · {link.score}%</div>
          <div className="pair">{link.a} <span style={{ color: tc }}>⇄</span> {link.b}</div>
          <div className="meter" style={{ marginTop: 12 }}>
            <motion.i
              style={{ background: `linear-gradient(90deg,color-mix(in srgb,${tc} 55%,transparent),${tc})` }}
              initial={{ width: 0 }}
              animate={{ width: `${link.score}%` }}
              transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1], delay: 0.15 }}
            />
          </div>
        </div>
        <div className="dbody">
          <p className="verline">Why this verdict: <b>{t.analogy}.</b> Every step below is recorded, sourced, and reversible.</p>
          <ul className="steps">
            {steps.map(([label, val, mono], i) => (
              <motion.li
                className="step"
                key={label}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.16 + i * 0.08, duration: 0.45 }}
              >
                <div className="node"><i /></div>
                <div className="t">{label}</div>
                <div className="c">{val}{mono && <span className="mono">{mono}</span>}</div>
              </motion.li>
            ))}
          </ul>
          <div className="caveat">{Ic.warn}<div><b style={{ color: "var(--amber)" }}>Limitation.</b> {c.caveat}</div></div>
          <div className="provbar">{link.prov.map((p) => <span className="prov" key={p}>{p}</span>)}</div>
          <div style={{ marginTop: 18, fontSize: 12.5, color: "var(--faint)" }}>
            Decision history: <span className="mono">proposed → needs_review</span> · analyst note required to accept.
          </div>
        </div>
      </motion.aside>
    </>
  );
}
