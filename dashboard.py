"""
Streamlit Dashboard for the PS 26151 prototype.

Provides a searchable, filterable analyst dashboard reading from
darkweb_intel.db. Follows the UI flow defined in docs/App_Flow.md.

USAGE:
    streamlit run dashboard.py
"""
import streamlit as st
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime, date

# --- Configuration ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper", "darkweb_intel.db")
PAGE_TITLE = "Dark Web Threat Actor Intelligence Dashboard"
CATEGORIES = ["All", "stolen_data", "arms", "hacking_services", "fraud", "money_laundering", "drugs"]

# --- Page config ---
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# Database helpers
# ============================================================

@st.cache_resource
def get_connection():
    """Return a shared SQLite connection (cached across reruns)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql, params=()):
    """Run a query and return a pandas DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


def query_rows(sql, params=()):
    """Run a query and return a list of Row objects."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def table_exists(table_name):
    """Check if a table exists in the database."""
    rows = query_rows(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return len(rows) > 0


def get_link_count(handle):
    """Get the number of relationship links for a given handle."""
    if not table_exists("relationship_links"):
        return 0
    rows = query_rows(
        "SELECT COUNT(*) as cnt FROM relationship_links WHERE actor_a = ? OR actor_b = ?",
        (handle, handle)
    )
    return rows[0]["cnt"] if rows else 0


# ============================================================
# Custom CSS
# ============================================================

st.markdown("""
<style>
    /* Dark theme inspired by terminal/hacker aesthetic */
    .stApp {
        background-color: #0a0a0a;
    }
    .metric-card {
        background: #1a1a2e;
        border: 1px solid #16213e;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .metric-value {
        font-size: 2em;
        font-weight: bold;
        color: #00ff88;
    }
    .metric-label {
        font-size: 0.9em;
        color: #8888aa;
    }
    .link-card {
        background: #1a1a2e;
        border-left: 4px solid;
        border-radius: 5px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .link-shared {
        border-left-color: #00ff88;
    }
    .link-stylometric {
        border-left-color: #ff6b6b;
    }
    .link-infra {
        border-left-color: #4ecdc4;
    }
    .evidence-text {
        color: #aaaacc;
        font-size: 0.85em;
        font-style: italic;
    }
    .confidence-high {
        color: #00ff88;
        font-weight: bold;
    }
    .confidence-medium {
        color: #ffd93d;
        font-weight: bold;
    }
    .confidence-low {
        color: #ff6b6b;
        font-weight: bold;
    }
    .post-item {
        background: #111122;
        border-radius: 5px;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-left: 2px solid #333355;
    }
    .section-header {
        color: #00ff88;
        border-bottom: 1px solid #333355;
        padding-bottom: 5px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper functions
# ============================================================

def confidence_class(score):
    if score >= 90:
        return "confidence-high"
    elif score >= 70:
        return "confidence-medium"
    else:
        return "confidence-low"


def confidence_emoji(score):
    if score >= 90:
        return "🟢"
    elif score >= 70:
        return "🟡"
    else:
        return "🔴"


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.markdown("## 🔍 Dark Web Intel")
    st.markdown("**PS 26151 Prototype**")
    st.markdown("---")

    # Quick stats
    if os.path.exists(DB_PATH):
        actors_count = query_rows("SELECT COUNT(*) as cnt FROM actors")[0]["cnt"]
        posts_count = query_rows("SELECT COUNT(*) as cnt FROM posts")[0]["cnt"]

        links_count = 0
        if table_exists("relationship_links"):
            links_count = query_rows("SELECT COUNT(*) as cnt FROM relationship_links")[0]["cnt"]

        infra_count = 0
        if table_exists("infra_links"):
            infra_count = query_rows("SELECT COUNT(*) as cnt FROM infra_links")[0]["cnt"]

        st.metric("Actors Tracked", actors_count)
        st.metric("Posts Collected", posts_count)
        st.metric("Relationship Links", links_count)
        st.metric("Infra Matches", infra_count)
    else:
        st.error("Database not found!")

    st.markdown("---")
    st.markdown("*Built for NTRO — Blockchain & Cybersecurity*")


# ============================================================
# Check database
# ============================================================

if not os.path.exists(DB_PATH):
    st.error(f"❌ Database not found at `{DB_PATH}`")
    st.info("Run the scraper first to create the database, then run `run_pipeline.py`.")
    st.stop()


# ============================================================
# Navigation
# ============================================================

if "selected_actor" not in st.session_state:
    st.session_state.selected_actor = None


def show_actor_profile(handle):
    st.session_state.selected_actor = handle


def go_back():
    st.session_state.selected_actor = None


# ============================================================
# SCREEN 2: Actor Profile
# ============================================================

if st.session_state.selected_actor is not None:
    handle = st.session_state.selected_actor

    # Back button
    st.button("← Back to Search", on_click=go_back, type="primary")

    # Fetch actor data
    actor_rows = query_rows("SELECT * FROM actors WHERE handle = ?", (handle,))

    if not actor_rows:
        st.error(f"Actor '{handle}' not found.")
        st.stop()

    actor = actor_rows[0]

    # --- Header ---
    st.markdown(f"# 👤 {actor['handle']}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**Category:** `{actor['category']}`")
    with col2:
        st.markdown(f"**Source:** `{actor['source']}`")
    with col3:
        status_emoji = "🟢" if actor['status'] == 'active' else "🔴"
        st.markdown(f"**Status:** {status_emoji} `{actor['status']}`")
    with col4:
        st.markdown(f"**Last Seen:** `{actor['last_seen']}`")

    st.markdown("---")

    # --- Identifiers ---
    st.markdown("### 🔑 Identifiers")
    id_col1, id_col2 = st.columns(2)
    with id_col1:
        pgp = actor['pgp_fingerprint'] or "None"
        st.code(f"PGP Fingerprint: {pgp}", language=None)
    with id_col2:
        wallet = actor['wallet_address'] or "None"
        st.code(f"Wallet Address: {wallet}", language=None)

    st.markdown("---")

    # --- Linked Personas ---
    st.markdown("### 🔗 Linked Personas")

    if table_exists("relationship_links"):
        links = query_df("""
            SELECT actor_a, actor_b, link_type, evidence, confidence_score
            FROM relationship_links
            WHERE actor_a = ? OR actor_b = ?
            ORDER BY confidence_score DESC
        """, (handle, handle))

        if not links.empty:
            # Group by link type
            shared_links = links[links['link_type'] == 'shared_identifier']
            style_links = links[links['link_type'] == 'stylometric']

            if not shared_links.empty:
                st.markdown("#### 🔐 Linked via Shared Identifier")
                for _, link in shared_links.iterrows():
                    other = link['actor_b'] if link['actor_a'] == handle else link['actor_a']
                    emoji = confidence_emoji(link['confidence_score'])
                    st.markdown(f"""
<div class="link-card link-shared">
    <strong>{other}</strong> &nbsp; {emoji} <span class="{confidence_class(link['confidence_score'])}">Confidence: {link['confidence_score']}%</span><br>
    <span class="evidence-text">📋 {link['evidence']}</span>
</div>
                    """, unsafe_allow_html=True)

            if not style_links.empty:
                st.markdown("#### 🧠 Linked via Writing Style (AI Stylometry)")
                for _, link in style_links.iterrows():
                    other = link['actor_b'] if link['actor_a'] == handle else link['actor_a']
                    emoji = confidence_emoji(link['confidence_score'])
                    st.markdown(f"""
<div class="link-card link-stylometric">
    <strong>{other}</strong> &nbsp; {emoji} <span class="{confidence_class(link['confidence_score'])}">Confidence: {link['confidence_score']}%</span><br>
    <span class="evidence-text">🧠 {link['evidence']}</span><br>
    <span class="evidence-text">⚠️ This pair shares NO PGP key or wallet — this link was found through AI stylometric analysis only.</span>
</div>
                    """, unsafe_allow_html=True)

            if shared_links.empty and style_links.empty:
                st.info("No linked personas found for this actor.")
        else:
            st.info("No linked personas found for this actor.")
    else:
        st.warning("Relationship links table not found. Run `run_pipeline.py` first.")

    st.markdown("---")

    # --- Infrastructure Matches ---
    st.markdown("### 🌐 Infrastructure Correlation")

    if table_exists("infra_links"):
        infra = query_df("SELECT * FROM infra_links")

        if not infra.empty:
            for _, match in infra.iterrows():
                emoji = confidence_emoji(match['confidence_score'])
                st.markdown(f"""
<div class="link-card link-infra">
    <strong>Onion:</strong> <code>{match['onion_address']}</code><br>
    <strong>Clearnet:</strong> <code>{match['clearnet_host']}</code><br>
    {emoji} <span class="{confidence_class(match['confidence_score'])}">Confidence: {match['confidence_score']}%</span><br>
    <span class="evidence-text">🔗 {match['evidence']}</span>
</div>
                """, unsafe_allow_html=True)
        else:
            st.info("No infrastructure matches found. Run `match_infra.py` first.")
    else:
        st.info("Infrastructure links table not found. Run `db_setup.py` first.")

    st.markdown("---")

    # --- Raw Posts ---
    st.markdown("### 💬 Posts / Activity")
    posts = query_df(
        "SELECT timestamp, text FROM posts WHERE handle = ? ORDER BY timestamp DESC",
        (handle,)
    )

    if not posts.empty:
        for _, post in posts.iterrows():
            ts = post['timestamp'] if post['timestamp'] else "Unknown"
            st.markdown(f"""
<div class="post-item">
    <small>🕐 {ts}</small><br>
    {post['text']}
</div>
            """, unsafe_allow_html=True)
    else:
        st.info("No posts found for this actor.")

    st.markdown("---")

    # --- Export this actor ---
    st.markdown("### 📥 Export This Actor's Profile")
    export_col1, export_col2 = st.columns(2)

    # Build export data
    actor_data = dict(actor)
    actor_data['links'] = []
    if table_exists("relationship_links"):
        link_rows = query_rows("""
            SELECT actor_a, actor_b, link_type, evidence, confidence_score
            FROM relationship_links WHERE actor_a = ? OR actor_b = ?
        """, (handle, handle))
        for lr in link_rows:
            actor_data['links'].append(dict(lr))

    actor_data['posts'] = []
    post_rows = query_rows("SELECT timestamp, text FROM posts WHERE handle = ?", (handle,))
    for pr in post_rows:
        actor_data['posts'].append(dict(pr))

    with export_col1:
        # CSV export
        export_df = pd.DataFrame([{
            'handle': actor['handle'],
            'category': actor['category'],
            'source': actor['source'],
            'status': actor['status'],
            'last_seen': actor['last_seen'],
            'pgp_fingerprint': actor['pgp_fingerprint'],
            'wallet_address': actor['wallet_address'],
            'linked_actors': ", ".join([
                (l['actor_b'] if l['actor_a'] == handle else l['actor_a'])
                for l in (link_rows if table_exists("relationship_links") else [])
            ]),
            'num_posts': len(post_rows)
        }])
        csv = export_df.to_csv(index=False)
        st.download_button(
            "📄 Download CSV",
            csv,
            file_name=f"actor_{handle}.csv",
            mime="text/csv"
        )

    with export_col2:
        # JSON export
        json_str = json.dumps(actor_data, indent=2, default=str)
        st.download_button(
            "📋 Download JSON",
            json_str,
            file_name=f"actor_{handle}.json",
            mime="application/json"
        )


# ============================================================
# SCREEN 1: Search / Home
# ============================================================

else:
    st.markdown(f"# 🔍 {PAGE_TITLE}")
    st.markdown("*Search, filter, and analyze threat actor intelligence from the mock dark web lab.*")

    # --- Search and Filters ---
    filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 2])

    with filter_col1:
        search_query = st.text_input(
            "🔎 Search by handle, category, or identifier",
            placeholder="e.g. DarkFox, Nightshade99, stolen_data..."
        )

    with filter_col2:
        selected_category = st.selectbox("📂 Category", CATEGORIES)

    with filter_col3:
        # Date range
        all_dates = query_df("SELECT MIN(last_seen) as min_d, MAX(last_seen) as max_d FROM actors")
        try:
            min_date = datetime.strptime(all_dates.iloc[0]['min_d'], "%Y-%m-%d").date()
            max_date = datetime.strptime(all_dates.iloc[0]['max_d'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            min_date = date(2026, 1, 1)
            max_date = date(2026, 12, 31)

        date_range = st.date_input(
            "📅 Last seen range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    # --- Build query ---
    conditions = []
    params = []

    if search_query:
        conditions.append("""(
            handle LIKE ? OR category LIKE ? OR
            pgp_fingerprint LIKE ? OR wallet_address LIKE ? OR
            source LIKE ?
        )""")
        like_q = f"%{search_query}%"
        params.extend([like_q, like_q, like_q, like_q, like_q])

    if selected_category != "All":
        conditions.append("category = ?")
        params.append(selected_category)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        conditions.append("last_seen BETWEEN ? AND ?")
        params.extend([date_range[0].isoformat(), date_range[1].isoformat()])

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM actors WHERE {where_clause} ORDER BY last_seen DESC"

    actors_df = query_df(sql, tuple(params))

    # --- Results ---
    st.markdown("---")

    if actors_df.empty:
        st.warning("🔍 No matching actors found. Try adjusting your search or filters.")
    else:
        st.markdown(f"**Showing {len(actors_df)} actor(s)**")

        # Add link count column
        actors_df['linked_actors'] = actors_df['handle'].apply(get_link_count)

        # Display results as a table with clickable rows
        for idx, row in actors_df.iterrows():
            status_emoji = "🟢" if row['status'] == 'active' else "🔴"
            links_badge = f"🔗 {row['linked_actors']}" if row['linked_actors'] > 0 else ""

            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1.5, 1.2, 0.8, 1])

            with col1:
                st.button(
                    f"👤 {row['handle']}",
                    key=f"actor_{row['handle']}",
                    on_click=show_actor_profile,
                    args=(row['handle'],),
                    use_container_width=True
                )
            with col2:
                st.markdown(f"`{row['category']}`")
            with col3:
                st.markdown(f"`{row['source']}`")
            with col4:
                st.markdown(f"`{row['last_seen']}`")
            with col5:
                st.markdown(f"{status_emoji}")
            with col6:
                st.markdown(f"{links_badge}")

        st.markdown("---")

        # --- Bulk Export ---
        st.markdown("### 📥 Export Results")
        export_col1, export_col2 = st.columns(2)

        display_df = actors_df[['handle', 'category', 'source', 'status', 'last_seen',
                                'pgp_fingerprint', 'wallet_address', 'linked_actors']].copy()

        with export_col1:
            csv_data = display_df.to_csv(index=False)
            st.download_button(
                "📄 Export Filtered Results (CSV)",
                csv_data,
                file_name="dark_web_actors_export.csv",
                mime="text/csv",
                disabled=len(actors_df) == 0
            )

        with export_col2:
            json_data = display_df.to_json(orient="records", indent=2)
            st.download_button(
                "📋 Export Filtered Results (JSON)",
                json_data,
                file_name="dark_web_actors_export.json",
                mime="application/json",
                disabled=len(actors_df) == 0
            )
