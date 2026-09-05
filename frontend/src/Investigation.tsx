import { motion } from "framer-motion";
import { ACTORS, Link, LINKS, TIERS } from "./data";
import { Ic } from "./icons";

function plainDesc(l: Link) {
  if (l.tier === "insufficient") return "System rejected this — the shared wallet is a public mixer, not a real link.";
  return "Because " + l.chain.indicatorPlain + ".";
}

function LinkCard({ link, plain, onOpen }: { link: Link; plain: boolean; onOpen: (l: Link) => void }) {
  const t = TIERS[link.tier];
  const tc = `var(${t.v})`;
  return (
    <motion.div
      className="lcard"
      style={{ ["--tc" as any]: tc }}
      onClick={() => onOpen(link)}
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onOpen(link)}
      whileHover={{ y: -2 }}
      layout
    >
      <div className="stripe" />
      <div>
        <div className="who"><b>{link.b}</b></div>
        <span className="tier" style={{ ["--tc" as any]: tc }}><span className="d" />{t.label}</span>
        <div className="desc">
          {plain ? plainDesc(link) : `${link.chain.source} · ${link.chain.indicator}`}
          {link.boost && <>  ·  <span className="boost">▲ 2 independent signals</span></>}
          {link.cap && <>  ·  <span style={{ color: "var(--slate)" }}>capped — text only</span></>}
        </div>
      </div>
      <div className="score">
        <div className="n" style={{ color: tc }}>{link.score}%</div>
        <div className="l">confidence</div>
        <div className="catbadge" style={{ marginTop: 6 }}>{link.cat}</div>
      </div>
    </motion.div>
  );
}

export function Investigation({ plain, onOpen }: { plain: boolean; onOpen: (l: Link) => void }) {
  const a = ACTORS.DarkFox;
  const main = LINKS[0];
  const t = TIERS[main.tier];
  const tc = `var(${t.v})`;
  return (
    <div>
      <div className="search">{Ic.search}<input value="DarkFox" readOnly aria-label="search" /><span className="kbd">⌘K</span></div>

      <div className="verdict" style={{ ["--tc" as any]: tc }}>
        <div className="rail3" style={{ background: tc }} />
        <div className="eyebrow">Attribution verdict</div>
        <h2><b>DarkFox</b> is {t.label.toLowerCase()} as <b>DarkFox_v2</b></h2>
        <p>
          Both personas published the <em>same PGP key</em> and reused the <em>same wallet</em> across two listings on
          SecureVault Market — a hard, cryptographic overlap. {plain && 'In plain terms: the digital "signatures" they left behind match.'}
        </p>
        <div className="meterrow">
          <div className="meter">
            <motion.i
              style={{ background: `linear-gradient(90deg,color-mix(in srgb,${tc} 55%,transparent),${tc})` }}
              initial={{ width: 0 }} animate={{ width: `${main.score}%` }} transition={{ duration: 1.1, ease: [0.2, 0.8, 0.2, 1] }}
            />
          </div>
          <div className="pct" style={{ color: tc }}>{main.score}%</div>
        </div>
      </div>

      <div className="grid">
        <div>
          <div className="sectlabel"><h3>Linked personas</h3><span className="count">1 shown</span></div>
          <div className="links">
            <LinkCard link={LINKS[0]} plain={plain} onOpen={onOpen} />
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="sectlabel"><h3>Across the network</h3><span className="count">3 more</span></div>
            <div className="links">
              {LINKS.slice(1).map((l) => <LinkCard key={l.id} link={l} plain={plain} onOpen={onOpen} />)}
            </div>
          </div>
        </div>

        <aside className="idcard">
          <div className="idhead">
            <div className="ident" style={{ background: a.grad }}>DF</div>
            <div><h3>DarkFox</h3><div className="sub">Threat actor · profile</div></div>
          </div>
          <div className="kv">
            <div className="row"><span className="k">Category</span><span className="v">{a.cat}</span></div>
            <div className="row"><span className="k">Source market</span><span className="v">{a.market}</span></div>
            <div className="row"><span className="k">Status</span><span className="v" style={{ color: "var(--emerald)" }}>● {a.status}</span></div>
            <div className="row"><span className="k">Last seen</span><span className="v mono">{a.seen}</span></div>
            <div className="row"><span className="k">PGP</span><span className="v mono">{a.pgp.slice(0, 23)}…</span></div>
            <div className="row"><span className="k">Wallet</span><span className="v mono">{a.wallet.slice(0, 18)}…</span></div>
          </div>
          <div className="chiprow">
            <span className="chip">2 linked personas</span><span className="chip">4 evidence units</span><span className="chip">1 open case</span>
          </div>
        </aside>
      </div>

      <div className="foot">{Ic.shield}<div><b style={{ color: "var(--ink)" }}>What this system will never claim:</b> a real-world identity. Throughline connects <em>technical</em> personas using recorded evidence — it does not defeat Tor or name a person.</div></div>
    </div>
  );
}
