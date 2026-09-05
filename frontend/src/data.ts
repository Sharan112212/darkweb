// Demo fixtures + shared types. These render when the live API is unreachable
// or returns no rows, so the app always demonstrates well. When the FastAPI
// backend is populated, api.ts prefers live data automatically.

export type TierKey =
  | "observed_technical_identity"
  | "likely_same_actor"
  | "possible_association"
  | "insufficient";

export interface Tier {
  label: string;
  short: string;
  v: string; // css var
  analogy: string;
}

export const TIERS: Record<TierKey, Tier> = {
  observed_technical_identity: { label: "Strong technical match", short: "Strong match", v: "--emerald", analogy: "Like matching fingerprints" },
  likely_same_actor: { label: "Likely the same operator", short: "Likely same", v: "--amber", analogy: "Strong circumstantial evidence" },
  possible_association: { label: "Possibly connected", short: "Possible", v: "--slate", analogy: "A lead worth investigating" },
  insufficient: { label: "Not enough evidence", short: "Insufficient", v: "--grey", analogy: "The system refuses to guess" },
};

export interface EvidenceChain {
  source: string;
  indicator: string;
  indicatorPlain: string;
  value: string;
  reliability: string;
  contribution: string;
  when: string;
  caveat: string;
}

export interface Link {
  id: string;
  a: string;
  b: string;
  tier: TierKey;
  score: number;
  cat: string;
  boost?: boolean;
  cap?: boolean;
  chain: EvidenceChain;
  prov: string[];
}

export interface Actor {
  cat: string;
  market: string;
  status: string;
  seen: string;
  pgp: string;
  wallet: string;
  grad: string;
}

export const ACTORS: Record<string, Actor> = {
  DarkFox: { cat: "stolen_data", market: "SecureVault Market", status: "active", seen: "2026-07-02", pgp: "9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77", wallet: "bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6", grad: "linear-gradient(140deg,#f6b93b,#f2607a)" },
  DarkFox_v2: { cat: "stolen_data", market: "SecureVault Market", status: "active", seen: "2026-08-10", pgp: "9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77", wallet: "bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6", grad: "linear-gradient(140deg,#f6b93b,#38e0cf)" },
};

export const LINKS: Link[] = [
  {
    id: "l1", a: "DarkFox", b: "DarkFox_v2", tier: "likely_same_actor", score: 95, cat: "K",
    chain: {
      source: "Identity Graph", indicator: "PGP fingerprint",
      indicatorPlain: "a unique cryptographic signature both accounts published",
      value: "9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77",
      reliability: "High — deterministic string match", contribution: "Category K · weight 0.95",
      when: "Observed Jul 2026 · Captured 10 Aug 2026",
      caveat: "A published key proves both accounts posted it — not that the same person holds the private key.",
    },
    prov: ["ev_os_9a3f21", "cap_market_a_07", "sha256:1b4c…d90", "identity_graph v1.0"],
  },
  {
    id: "l2", a: "ViperX", b: "ViperX_Reborn", tier: "observed_technical_identity", score: 98, cat: "K+S", boost: true,
    chain: {
      source: "Identity Graph + Stylometry", indicator: "shared wallet + writing style",
      indicatorPlain: "the same crypto wallet AND matching writing style — two independent signals",
      value: "1ViperX8888…  ·  cosine 0.84", reliability: "High — two independent categories agree",
      contribution: "K 0.90 combined with S 0.60 (noisy-OR)", when: "Observed May–Aug 2026",
      caveat: "Two independent signals raise confidence — but writing style alone would never be enough.",
    },
    prov: ["ev_id_77aa", "ev_sty_2c4d", "cap_market_b_06", "fusion v1.0"],
  },
  {
    id: "l3", a: "GhostVendor", b: "Nightshade99", tier: "possible_association", score: 64, cat: "S", cap: true,
    chain: {
      source: "Stylometry (MiniLM)", indicator: "semantic writing-style similarity",
      indicatorPlain: "their posts read similarly — same tone and vocabulary",
      value: "cosine similarity 0.82", reliability: "Medium — supporting evidence only",
      contribution: 'Category S · capped at "Possibly connected"', when: "Observed Apr–Aug 2026",
      caveat: 'Writing-style similarity ALONE cannot exceed "Possibly connected". It is supporting evidence, not proof of authorship — style can be copied or coincidental.',
    },
    prov: ["ev_sty_88fe", "cap_forum_04", "all-MiniLM-L6-v2", "fusion v1.0"],
  },
  {
    id: "l4", a: "cipherqueen", b: "moneymule_88", tier: "insufficient", score: 18, cat: "K·flagged",
    chain: {
      source: "Identity Graph", indicator: "shared wallet — flagged as mixer",
      indicatorPlain: "they used the same wallet, but it is a known money-mixing service used by many unrelated people",
      value: "wallet role: mixer_suspected", reliability: "Low — non-exclusive indicator",
      contribution: "Down-weighted to ~0 · not a link", when: "Observed Aug 2026",
      caveat: "A shared mixing/exchange wallet does NOT link two actors — thousands of unrelated people use it. The system deliberately rejects this false positive.",
    },
    prov: ["ev_id_31ac", "wallet_intel", "fusion v1.0"],
  },
];

export const NODES: Record<string, [number, number]> = {
  DarkFox: [190, 150], DarkFox_v2: [430, 110],
  ViperX: [760, 150], ViperX_Reborn: [900, 300],
  GhostVendor: [300, 430], Nightshade99: [560, 470],
  cipherqueen: [720, 420], moneymule_88: [880, 500],
};

export interface TLItem { when: string; tier: TierKey; title: string; d: string; approx?: boolean; }
export const TL: TLItem[] = [
  { when: "2026-04-02", tier: "possible_association", title: "GhostVendor first seen", d: "First post on Obsidian Forum (arms)." },
  { when: "2026-05-10", tier: "possible_association", title: "GhostVendor goes quiet", d: '"Closing shop for a bit… too much heat." Last post.', approx: true },
  { when: "2026-06-25", tier: "possible_association", title: "Nightshade99 appears", d: "New alias, same forum, matching tone & vocabulary." },
  { when: "2026-07-02", tier: "likely_same_actor", title: "DarkFox ⇄ DarkFox_v2 linked", d: "Shared PGP + wallet detected — candidate link created." },
  { when: "2026-08-20", tier: "observed_technical_identity", title: "ViperX ⇄ ViperX_Reborn confirmed", d: "Two independent signals agree — score boosted to 98%." },
];
