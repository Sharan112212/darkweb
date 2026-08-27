"""
Analyst Feedback Statistics Engine for the PS 26151 prototype.

Computes historical reliability metrics per link_type based on
analyst confirmations/rejections in link_feedback.

USAGE:
    python feedback_stats.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "scraper", "darkweb_intel.db")


def get_feedback_stats():
    """Fetch feedback statistics per link_type from the database."""
    if not os.path.exists(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='link_feedback'")
    if not cur.fetchone():
        conn.close()
        return {}

    # Query feedback combined with link_type from relationship_links
    cur.execute("""
        SELECT 
            r.link_type,
            COUNT(f.id) as total_feedback,
            SUM(CASE WHEN f.feedback = 'confirmed' THEN 1 ELSE 0 END) as confirmed_count,
            SUM(CASE WHEN f.feedback = 'rejected' THEN 1 ELSE 0 END) as rejected_count
        FROM link_feedback f
        JOIN relationship_links r ON f.link_id = r.id
        WHERE f.link_source = 'relationship_links'
        GROUP BY r.link_type
    """)

    rows = cur.fetchall()
    stats = {}

    for row in rows:
        ltype = row['link_type']
        total = row['total_feedback']
        conf = row['confirmed_count'] or 0
        rej = row['rejected_count'] or 0
        rel_pct = int(round((conf / total) * 100)) if total > 0 else 0

        stats[ltype] = {
            'total': total,
            'confirmed': conf,
            'rejected': rej,
            'reliability_pct': rel_pct
        }

    conn.close()
    return stats


def print_feedback_summary():
    """Print analyst feedback reliability summary table."""
    print("\n" + "=" * 60)
    print("  ANALYST FEEDBACK & SIGNAL RELIABILITY STATS")
    print("=" * 60)

    stats = get_feedback_stats()

    if not stats:
        print("  No analyst feedback recorded yet.")
        print("  (Analyst confirmations via dashboard will update these metrics.)")
        print("=" * 60)
        return

    print(f"  {'Link Type':22s} | Confirmed | Rejected | Reliability")
    print("  " + "-" * 56)
    for ltype, data in stats.items():
        print(f"  {ltype:22s} | {data['confirmed']:9d} | {data['rejected']:8d} | {data['reliability_pct']}%")
    print("=" * 60)


if __name__ == "__main__":
    print_feedback_summary()
