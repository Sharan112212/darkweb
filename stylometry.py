"""
Stylometry Module for the PS 26151 prototype.

Uses Sentence-BERT (all-MiniLM-L6-v2) to embed each actor's combined
posts, then computes pairwise cosine similarity to detect writing-style
matches between actors that share NO identifiers. Writes high-confidence
matches into the relationship_links table.

USAGE:
    python stylometry.py
"""
import sqlite3
import os
import warnings
from itertools import combinations

# Suppress noisy warnings from transformers
warnings.filterwarnings("ignore", category=FutureWarning)

DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")

# Similarity threshold: pairs scoring above this are written to DB.
# Start at 0.75 as suggested in TRD — tune after seeing results.
SIMILARITY_THRESHOLD = 0.75

# Model name — runs on CPU, no GPU needed
MODEL_NAME = "all-MiniLM-L6-v2"


def run_stylometry():
    # Import here so the script prints a helpful error if not installed
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        print("[!] sentence-transformers not installed.")
        print("    Run: pip install sentence-transformers")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- Load posts grouped by handle ---
    cur.execute("SELECT handle, text FROM posts ORDER BY handle")
    rows = cur.fetchall()

    if not rows:
        print("[!] No posts found in database. Run the scraper first.")
        conn.close()
        return 0

    # Concatenate each actor's posts into one text blob
    actor_texts = {}
    for handle, text in rows:
        if text and text.strip():
            if handle not in actor_texts:
                actor_texts[handle] = []
            actor_texts[handle].append(text.strip())

    filtered_actor_texts = {}
    for handle, t_list in actor_texts.items():
        combined = " ".join(t_list).strip()
        if combined:
            filtered_actor_texts[handle] = combined

    if not filtered_actor_texts:
        print("[!] No valid post text found for any actor.")
        conn.close()
        return 0

    handles = list(filtered_actor_texts.keys())
    texts = [filtered_actor_texts[h] for h in handles]

    LOCAL_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "all-MiniLM-L6-v2")
    if os.path.exists(LOCAL_MODEL_DIR):
        print(f"[*] Loading pre-cached local Sentence-BERT model from: {LOCAL_MODEL_DIR}")
        model = SentenceTransformer(LOCAL_MODEL_DIR)
    else:
        print(f"[*] Loading Sentence-BERT model ({MODEL_NAME})...")
        model = SentenceTransformer(MODEL_NAME)

    print(f"[*] Computing embeddings for {len(handles)} actors...")
    embeddings = model.encode(texts, convert_to_tensor=True)

    # --- Get existing stylometric links to avoid duplicates on re-run ---
    cur.execute("SELECT actor_a, actor_b FROM relationship_links WHERE link_type = 'stylometric'")
    existing_style_links = set()
    for a, b in cur.fetchall():
        existing_style_links.add((min(a, b), max(a, b)))

    # --- Compute pairwise cosine similarity ---
    print("[*] Computing pairwise similarity...")
    all_pairs = []
    for i, j in combinations(range(len(handles)), 2):
        sim = util.cos_sim(embeddings[i], embeddings[j]).item()
        pair_key = (min(handles[i], handles[j]), max(handles[i], handles[j]))
        all_pairs.append((handles[i], handles[j], sim, pair_key))

    # Sort by similarity descending
    all_pairs.sort(key=lambda x: x[2], reverse=True)

    # --- Print top 10 pairs for threshold calibration ---
    print("\n[*] Top 10 most similar actor pairs (for 0.75 threshold calibration):")
    print("    " + "-" * 65)
    for idx, (a, b, sim, pair_key) in enumerate(all_pairs[:10], 1):
        status_flag = "  [MATCH >= 0.75]" if sim >= SIMILARITY_THRESHOLD else "  [BELOW THRESHOLD]"
        already_linked = " (already in DB)" if pair_key in existing_style_links else ""
        print(f"    {idx:2d}. {a:18s} <-> {b:18s}  similarity: {sim:.4f}{status_flag}{already_linked}")
    print("    " + "-" * 65)
    print(f"    Active Threshold: {SIMILARITY_THRESHOLD}")

    # --- Write matches above threshold ---
    links_created = 0
    for a, b, sim, pair_key in all_pairs:
        if sim < SIMILARITY_THRESHOLD:
            break  # sorted descending, so all remaining are below threshold

        if pair_key in existing_style_links:
            continue  # skip if stylometric link already recorded

        confidence = int(round(sim * 100))
        evidence = f"Writing style similarity score: {sim:.4f} (Sentence-BERT cosine similarity)"

        try:
            cur.execute("""
                INSERT OR IGNORE INTO relationship_links
                (actor_a, actor_b, link_type, evidence, confidence_score)
                VALUES (?, ?, 'stylometric', ?, ?)
            """, (pair_key[0], pair_key[1], evidence, confidence))
            if cur.rowcount > 0:
                links_created += 1
                print(f"[+] Linked {pair_key[0]} <-> {pair_key[1]} (stylometric, confidence {confidence}%)")
        except sqlite3.Error as e:
            print(f"[!] Error linking {pair_key[0]} <-> {pair_key[1]}: {e}")

    conn.commit()
    conn.close()

    print(f"\n[*] Stylometry complete. {links_created} new link(s) created.")
    return links_created


if __name__ == "__main__":
    run_stylometry()
