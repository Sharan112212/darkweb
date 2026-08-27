"""
Pipeline runner for the PS 26151 prototype.

Runs all analysis modules in sequence:
  1. db_setup.py      — extends the schema
  2. identity_graph.py — links actors by shared PGP/wallet
  3. stylometry.py     — links actors by writing style

NOTE: The scraper (scraper.py) and infra-matcher (match_infra.py) are NOT
included here because they require onion addresses as arguments and a
running Tor connection. Run those manually first:
  - python scraper/scraper.py --onion <marketplace>.onion
  - python infra-matcher/match_infra.py --onion <vulnerable>.onion

USAGE:
    python run_pipeline.py
"""
import sqlite3
import os
import sys
import time

# Ensure we run from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join("scraper", "darkweb_intel.db")


def print_banner(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def run_step(step_name, module_func):
    """Run a pipeline step and time it."""
    print_banner(step_name)
    start = time.time()
    try:
        result = module_func()
        elapsed = time.time() - start
        print(f"    Completed in {elapsed:.1f}s")
        return result
    except Exception as e:
        print(f"[!] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_summary():
    """Print final summary of all tables."""
    print_banner("PIPELINE SUMMARY")

    if not os.path.exists(DB_PATH):
        print("[!] Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables_info = [
        ("actors", "Actor profiles from scraper"),
        ("posts", "Forum/marketplace posts"),
        ("relationship_links", "Identity + stylometry links"),
        ("fused_links", "Multi-signal fused confidence links"),
        ("infra_links", "Infrastructure correlation matches"),
        ("link_feedback", "Analyst feedback entries"),
    ]

    for table_name, description in tables_info:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"    {table_name:25s}  {count:4d} rows   ({description})")
        except sqlite3.OperationalError:
            print(f"    {table_name:25s}     — table not found")

    # Show specific fused links
    print("\n  Multi-Signal Fused Links detail:")
    try:
        cur.execute("""
            SELECT actor_a, actor_b, fused_confidence, signal_count, contributing_link_types
            FROM fused_links
            ORDER BY fused_confidence DESC
        """)
        fused = cur.fetchall()
        if fused:
            for a, b, score, scount, stypes in fused:
                boost = " [BOOSTED MULTI-SIGNAL]" if scount > 1 else ""
                print(f"    {a:20s} <-> {b:20s}  fused: {score}%  (signals: {scount} [{stypes}]){boost}")
        else:
            print("    (no fused links found)")
    except sqlite3.OperationalError:
        print("    (fused_links table not available)")

    conn.close()


if __name__ == "__main__":
    print_banner("DARK WEB ANALYSIS PIPELINE — PS 26151")
    print("  Running all analysis modules in sequence...")

    # Check database exists
    if not os.path.exists(DB_PATH):
        print(f"\n[!] Database not found at {DB_PATH}")
        print("    Run the scraper first:")
        print("    python scraper/scraper.py --onion <marketplace>.onion")
        sys.exit(1)

    # Step 1: Extend schema
    from db_setup import setup_schema
    run_step("Step 1: Extending database schema", setup_schema)

    # Step 2: Identity graph
    from identity_graph import run_identity_graph
    run_step("Step 2: Building identity graph (PGP/wallet matching)", run_identity_graph)

    # Step 3: Stylometry
    from stylometry import run_stylometry
    run_step("Step 3: Running stylometric analysis (AI writing style)", run_stylometry)

    # Step 4: Multi-signal Fusion
    from fusion import run_fusion
    run_step("Step 4: Running Multi-Signal Fusion engine (Noisy-OR)", run_fusion)

    # Final summary
    print_summary()

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("  Next steps:")
    print("    1. Run infra-matcher if not already done:")
    print("       python infra-matcher/match_infra.py --onion <vulnerable>.onion")
    print("    2. Launch dashboard:")
    print("       streamlit run dashboard.py")
    print("=" * 60)
