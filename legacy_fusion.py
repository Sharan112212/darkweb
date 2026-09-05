"""
Legacy Multi-Signal Fusion Module for the PS 26151 prototype.

NOTE: renamed from ``fusion.py`` so it no longer collides with the Branch 3
``fusion/`` package (the explainable K/I/B/S engine). This standalone module
remains the simple Noisy-OR runner used by ``run_pipeline.py`` for the offline
demo; the ``fusion/`` package supersedes it for the full pipeline.

Fuses independent attribution signals (shared identifiers, AI stylometry)
for actor pairs into a single, unified confidence score using Noisy-OR combination:
  fused_confidence = 1 - Π(1 - confidence_i / 100)  [as a percentage]

Writes results into the `fused_links` table in darkweb_intel.db.

USAGE:
    python fusion.py
"""
import sqlite3
import os
import math

DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")


def run_fusion():
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if relationship_links table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationship_links'")
    if not cur.fetchone():
        print("[!] relationship_links table not found. Run pipeline steps 1-3 first.")
        conn.close()
        return 0

    # Fetch all relationship links
    cur.execute("""
        SELECT actor_a, actor_b, link_type, evidence, confidence_score
        FROM relationship_links
    """)
    rows = cur.fetchall()

    if not rows:
        print("[!] No relationship links found to fuse.")
        conn.close()
        return 0

    # Group links by pair
    pair_links = {}
    for a, b, link_type, evidence, confidence in rows:
        pair_key = (min(a, b), max(a, b))
        if pair_key not in pair_links:
            pair_links[pair_key] = []
        pair_links[pair_key].append({
            'link_type': link_type,
            'evidence': evidence,
            'confidence': confidence
        })

    fused_records = []

    for (a, b), links in pair_links.items():
        actor_a_norm, actor_b_norm = min(a, b), max(a, b)
        confidences = [l['confidence'] for l in links]
        link_types = list(dict.fromkeys([l['link_type'] for l in links]))  # preserve order, unique
        
        # Noisy-OR combination formula: 1 - Π(1 - c_i)
        prob_not_linked = 1.0
        for c in confidences:
            prob_not_linked *= (1.0 - (c / 100.0))
        
        fused_prob = 1.0 - prob_not_linked
        fused_confidence = int(round(fused_prob * 100.0))
        
        # Cap at 99% unless a single signal is 100%
        if fused_confidence > 99 and max(confidences) < 100:
            fused_confidence = 99

        contributing_types_str = ",".join(link_types)
        signal_count = len(link_types)
        
        evidence_lines = [f"[{l['link_type']}] (conf: {l['confidence']}%): {l['evidence']}" for l in links]
        evidence_summary = " | ".join(evidence_lines)

        fused_records.append((actor_a_norm, actor_b_norm, fused_confidence, contributing_types_str, signal_count, evidence_summary))

    # Write to fused_links table
    cur.executemany("""
        INSERT OR REPLACE INTO fused_links
        (actor_a, actor_b, fused_confidence, contributing_link_types, signal_count, evidence_summary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, fused_records)

    conn.commit()

    # Print summary
    print(f"[*] Fused {len(fused_records)} actor pair(s) across independent signals:")
    print("    " + "-" * 75)
    print(f"    {'Actor A':18s} <-> {'Actor B':18s} | {'Fused Conf':10s} | Signals | Types")
    print("    " + "-" * 75)

    fused_records.sort(key=lambda x: x[2], reverse=True)
    for a, b, conf, types, count, _ in fused_records:
        boost_indicator = " [BOOSTED]" if count > 1 else ""
        print(f"    {a:18s} <-> {b:18s} | {conf:3d}%       | {count:7d} | {types}{boost_indicator}")
    print("    " + "-" * 75)

    conn.close()
    return len(fused_records)


if __name__ == "__main__":
    run_fusion()
