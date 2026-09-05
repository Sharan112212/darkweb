import { useState } from "react";
import { motion } from "framer-motion";
import { Link, LINKS, NODES, TIERS, TierKey } from "./data";

const MAIN = new Set(["DarkFox", "ViperX", "GhostVendor", "cipherqueen"]);

function dashFor(tier: TierKey) {
  if (tier === "insufficient") return "2 9";
  if (tier === "possible_association") return "9 7";
  return undefined;
}

export function GraphView({ onOpen }: { onOpen: (l: Link) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  const connected = (n: string) =>
    !hover || n === hover || LINKS.some((l) => (l.a === hover || l.b === hover) && (l.a === n || l.b === n));

  return (
    <div className="gwrap">
      <div className="ghint">Click any connection to open its evidence chain</div>
      <svg viewBox="0 0 1040 560" role="img" aria-label="Attribution network graph">
        {LINKS.map((l, i) => {
          const t = TIERS[l.tier];
          const tc = `var(${t.v})`;
          const [ax, ay] = NODES[l.a];
          const [bx, by] = NODES[l.b];
          const mx = (ax + bx) / 2;
          const my = (ay + by) / 2 - 40;
          const w = 2 + (l.score / 100) * 5;
          const d = `M${ax},${ay} Q${mx},${my} ${bx},${by}`;
          const vis = connected(l.a) && connected(l.b);
          return (
            <g key={l.id} style={{ opacity: vis ? 1 : 0.12, transition: "opacity .2s", cursor: "pointer" }} onClick={() => onOpen(l)}>
              <motion.path
                d={d} fill="none" stroke={tc} strokeWidth={w} strokeLinecap="round" strokeDasharray={dashFor(l.tier)}
                style={{ filter: `drop-shadow(0 0 6px color-mix(in srgb,${tc} 40%,transparent))` }}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1.1, delay: 0.1 + i * 0.12, ease: "easeInOut" }}
              />
              <path d={d} fill="none" stroke="transparent" strokeWidth={18} />
              <text className="glabel" x={mx} y={my + 6} textAnchor="middle" fill={tc}>{l.score}%</text>
            </g>
          );
        })}
        {Object.entries(NODES).map(([name, [x, y]], i) => {
          const isMain = MAIN.has(name);
          return (
            <motion.g
              key={name}
              style={{ opacity: connected(name) ? 1 : 0.2, transition: "opacity .2s", cursor: "pointer" }}
              onMouseEnter={() => setHover(name)}
              onMouseLeave={() => setHover(null)}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.15 + i * 0.05, type: "spring", stiffness: 300, damping: 18 }}
            >
              <circle cx={x} cy={y} r={isMain ? 26 : 20} fill="var(--surface2)" stroke="var(--accent)" strokeWidth={isMain ? 2 : 1.2}
                style={{ filter: isMain ? "drop-shadow(0 0 10px rgba(56,224,207,.35))" : "none" }} />
              <circle cx={x} cy={y} r={isMain ? 7 : 5} fill="var(--accent)" />
              <text className="gname" x={x} y={y + (isMain ? 46 : 40)} textAnchor="middle">{name}</text>
            </motion.g>
          );
        })}
      </svg>
      <div className="legend">
        <h4>Connection strength</h4>
        {(Object.entries(TIERS) as [TierKey, typeof TIERS[TierKey]][]).map(([k, t]) => (
          <div className="lg" key={k}>
            <span
              className="ln"
              style={{
                background: `var(${t.v})`,
                ...(k === "possible_association" ? { backgroundImage: `repeating-linear-gradient(90deg,var(${t.v}) 0 6px,transparent 6px 11px)` } : {}),
                ...(k === "insufficient" ? { backgroundImage: `repeating-linear-gradient(90deg,var(${t.v}) 0 2px,transparent 2px 6px)` } : {}),
              }}
            />
            {t.label}
          </div>
        ))}
      </div>
    </div>
  );
}
