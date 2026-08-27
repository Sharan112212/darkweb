"""
Identity Graph Module for the PS 26151 prototype.

Reads the actors table from darkweb_intel.db, finds actors sharing
the same PGP fingerprint or wallet address, and writes the linked
pairs into the relationship_links table.

USAGE:
    python identity_graph.py
"""
import sqlite3
import os
from itertools import combinations

DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")

# Confidence scores for exact matches (no ML needed — these are deterministic)
PGP_CONFIDENCE = 95
WALLET_CONFIDENCE = 90


def run_identity_graph():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    links_created = 0

    # --- Group by shared PGP fingerprint ---
    cur.execute("""
        SELECT pgp_fingerprint, GROUP_CONCAT(handle, '||')
        FROM actors
        WHERE pgp_fingerprint IS NOT NULL AND pgp_fingerprint != ''
        GROUP BY pgp_fingerprint
        HAVING COUNT(*) > 1
    """)

    for row in cur.fetchall():
        fingerprint = row[0]
        handles = row[1].split("||")
        for a, b in combinations(handles, 2):
            actor_a_norm, actor_b_norm = min(a, b), max(a, b)
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO relationship_links
                    (actor_a, actor_b, link_type, evidence, confidence_score)
                    VALUES (?, ?, 'shared_identifier', ?, ?)
                """, (actor_a_norm, actor_b_norm, f"Shared PGP fingerprint: {fingerprint}", PGP_CONFIDENCE))
                if cur.rowcount > 0:
                    links_created += 1
                    print(f"[+] Linked {actor_a_norm} <-> {actor_b_norm} (shared PGP fingerprint, confidence {PGP_CONFIDENCE}%)")
            except sqlite3.Error as e:
                print(f"[!] Error linking {actor_a_norm} <-> {actor_b_norm}: {e}")

    # --- Group by shared wallet address ---
    cur.execute("""
        SELECT wallet_address, GROUP_CONCAT(handle, '||')
        FROM actors
        WHERE wallet_address IS NOT NULL AND wallet_address != ''
        GROUP BY wallet_address
        HAVING COUNT(*) > 1
    """)

    for row in cur.fetchall():
        wallet = row[0]
        handles = row[1].split("||")
        for a, b in combinations(handles, 2):
            actor_a_norm, actor_b_norm = min(a, b), max(a, b)
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO relationship_links
                    (actor_a, actor_b, link_type, evidence, confidence_score)
                    VALUES (?, ?, 'shared_identifier', ?, ?)
                """, (actor_a_norm, actor_b_norm, f"Shared wallet address: {wallet}", WALLET_CONFIDENCE))
                if cur.rowcount > 0:
                    links_created += 1
                    print(f"[+] Linked {actor_a_norm} <-> {actor_b_norm} (shared wallet address, confidence {WALLET_CONFIDENCE}%)")
            except sqlite3.Error as e:
                print(f"[!] Error linking {actor_a_norm} <-> {actor_b_norm}: {e}")

    conn.commit()
    conn.close()

    print(f"\n[*] Identity graph complete. {links_created} new link(s) created.")
    return links_created


if __name__ == "__main__":
    run_identity_graph()
