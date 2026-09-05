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


def record_feedback(link_id, link_source, feedback_val, analyst_note=None):
    """Record analyst feedback (confirmed/rejected) with a mandatory note (EC-26)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO link_feedback (link_id, link_source, feedback, analyst_note)
        VALUES (?, ?, ?, ?)
    """, (link_id, link_source, feedback_val, analyst_note))
    conn.commit()


# ============================================================
# Branch 5 — RBAC + disclosure + evidence drawer helpers
# ============================================================

DISCLOSURE_TEXT = (
    "This system provides confidence-scored technical associations for authorized "
    "analyst review. It does not defeat Tor, establish a person's real-world identity, "
    "or replace legal/forensic investigation."
)

# Role hierarchy mirrors api/rbac.py
ROLE_LEVEL = {"viewer": 1, "analyst": 2, "reviewer": 3, "admin": 4}


def current_role():
    return st.session_state.get("role", "analyst")


def can_decide():
    """Only analyst and above may accept/reject links (EC-26)."""
    return ROLE_LEVEL.get(current_role(), 1) >= ROLE_LEVEL["analyst"]


def render_decision_ui(link_id, other, key_prefix):
    """Mandatory-note decision UI, gated by role. Returns nothing; writes on submit."""
    if not can_decide():
        st.caption("🔒 Viewer role — decisions require Analyst permission or higher.")
        return
    note = st.text_input("Analyst note (required to record a decision)",
                         key=f"note_{key_prefix}_{link_id}",
                         placeholder="Why is this link confirmed or a false positive?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👍 Confirm", key=f"conf_{key_prefix}_{link_id}"):
            if not note.strip():
                st.warning("A note is required before recording a decision.")
            else:
                record_feedback(link_id, "relationship_links", "confirmed", note.strip())
                st.toast(f"Confirmed link with {other}.")
                st.rerun()
    with c2:
        if st.button("👎 False Positive", key=f"rej_{key_prefix}_{link_id}"):
            if not note.strip():
                st.warning("A note is required before recording a decision.")
            else:
                record_feedback(link_id, "relationship_links", "rejected", note.strip())
                st.toast(f"Flagged false positive for {other}.")
                st.rerun()


def render_evidence_drawer(link, other, key_prefix):
    """Evidence chain drawer: source -> indicator -> entities -> confidence -> caveat."""
    with st.expander(f"🔍 Evidence chain for link with {other}"):
        st.markdown(f"- **Link type / source:** `{link['link_type']}`")
        st.markdown(f"- **Linked entities:** `{link['actor_a']}` ↔ `{link['actor_b']}`")
        st.markdown(f"- **Confidence contribution:** `{link['confidence_score']}%`")
        if current_role() == "viewer":
            st.markdown("- **Observed indicator:** `[REDACTED — VIEW ONLY PERMISSION]`")
        else:
            st.markdown(f"- **Observed indicator / evidence:** {link['evidence']}")
        st.markdown(f"- **Link ID:** `{link['id']}`")
        if link['link_type'] == 'stylometric':
            st.caption("⚠️ Caveat: semantic similarity is supporting evidence only, not authorship proof.")


def render_timeline(handle):
    """
    Branch 6 timeline tab: chronological events for an actor built from the demo
    data (posts + relationship links). Uncertain times are visibly marked, and a
    date range filter is shared with the rest of the profile view.
    """
    events = []

    # post_observed events (observation time from the post)
    posts = query_rows("SELECT timestamp, text FROM posts WHERE handle = ?", (handle,))
    for p in posts:
        ts = (p["timestamp"] or "").strip()
        events.append({
            "type": "post_observed",
            "time": ts,
            "approximate": ts == "",
            "desc": (p["text"][:90] + "…") if p["text"] and len(p["text"]) > 90 else (p["text"] or ""),
        })

    # candidate_link_created events (from relationship links involving this actor)
    if table_exists("relationship_links"):
        links = query_rows(
            "SELECT created_at, link_type, actor_a, actor_b FROM relationship_links WHERE actor_a = ? OR actor_b = ?",
            (handle, handle),
        )
        for l in links:
            other = l["actor_b"] if l["actor_a"] == handle else l["actor_a"]
            events.append({
                "type": "candidate_link_created",
                "time": (l["created_at"] or "").strip(),
                "approximate": False,
                "desc": f"Link ({l['link_type']}) with {other}",
            })

    if not events:
        st.info("No timeline events available for this actor.")  # explicit absence (EC-39)
        return

    # Date range filter (shared bound the graph/search views also use)
    dated = [e for e in events if e["time"]]
    if dated:
        times = sorted(e["time"][:10] for e in dated)
        try:
            dmin = datetime.strptime(times[0], "%Y-%m-%d").date()
            dmax = datetime.strptime(times[-1], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            dmin, dmax = date(2026, 1, 1), date(2026, 12, 31)
        rng = st.date_input("📅 Timeline range", value=(dmin, dmax),
                            min_value=dmin, max_value=dmax, key=f"tl_range_{handle}")
        if isinstance(rng, tuple) and len(rng) == 2:
            lo, hi = rng[0].isoformat(), rng[1].isoformat()
            events = [e for e in events if (not e["time"]) or (lo <= e["time"][:10] <= hi)]

    icon = {"post_observed": "💬", "candidate_link_created": "🔗"}
    for e in sorted(events, key=lambda x: (x["time"] or "9999")):
        when = e["time"] if e["time"] else "unknown time"
        mark = " ⚠️ *approximate*" if e["approximate"] else ""
        st.markdown(f"- {icon.get(e['type'], '•')} **{when}**{mark} — _{e['type']}_: {e['desc']}")


def render_network_graph(center_handle=None):
    """
    Renders an interactive Pyvis 2D visual network graph in Streamlit (EC-38, Branch 5/10).
    Nodes = Threat actors / personas.
    Edges = Candidate links styled by tier/score.
    """
    import tempfile
    import streamlit.components.v1 as components
    from pyvis.network import Network
    from graph.networkx_projection import NetworkXProjection

    proj = NetworkXProjection()
    proj.sync_from_db(db_path=DB_PATH)

    if center_handle:
        subg = proj.get_subgraph(center_handle, depth=2, limit=50)
        nodes = subg.get("nodes", [])
        edges = subg.get("edges", [])
    else:
        full_proj = proj.get_projection()
        nodes = full_proj.get("nodes", [])
        edges = full_proj.get("edges", [])

    if not nodes or not edges:
        st.info("No network connections found to display in the graph.")
        return

    net = Network(height="450px", width="100%", bgcolor="#0a0a0a", font_color="#ffffff", directed=False)
    net.options.physics.enabled = True

    # Add nodes
    for n in nodes:
        nid = n["id"]
        is_center = (nid == center_handle)
        color = "#00ff88" if is_center else "#4ecdc4"
        size = 28 if is_center else 18
        net.add_node(nid, label=nid, title=f"Actor: {nid}", color=color, size=size)

    # Add edges
    for e in edges:
        u, v = e["source"], e["target"]
        score = float(e.get("score", 0.0))
        tier = e.get("tier", "unresolved")
        link_id = e.get("link_id", "")

        # Color by tier
        if score >= 0.85 or tier == "observed_technical_identity":
            edge_color = "#00ff88"  # Green
        elif score >= 0.65 or tier == "likely_same_actor":
            edge_color = "#ffd93d"  # Amber
        else:
            edge_color = "#8888aa"  # Grey

        width = max(1.5, score * 4)
        title = f"Link: {u} ↔ {v}\nScore: {score:.2f}\nTier: {tier}\nID: {link_id}"
        net.add_edge(u, v, value=score, title=title, color=edge_color, width=width)

    tmp_file = os.path.join(tempfile.gettempdir(), f"graph_{center_handle or 'all'}.html")
    net.save_graph(tmp_file)
    with open(tmp_file, "r", encoding="utf-8") as f:
        html_code = f.read()

    components.html(html_code, height=470, scrolling=False)


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

    # Branch 5 — role selection drives RBAC gating + redaction
    st.markdown("### Analyst Role")
    st.session_state.role = st.selectbox(
        "Acting role",
        ["viewer", "analyst", "reviewer", "admin"],
        index=["viewer", "analyst", "reviewer", "admin"].index(st.session_state.get("role", "analyst")),
        help="Viewer can browse but not decide; Analyst+ can record decisions.",
    )
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

        # Analyst Feedback Reliability Stats
        if table_exists("link_feedback") and table_exists("relationship_links"):
            st.markdown("---")
            st.markdown("### 📊 Signal Reliability")
            from feedback_stats import get_feedback_stats
            fb_stats = get_feedback_stats()
            if fb_stats:
                for ltype, data in fb_stats.items():
                    label = "Shared ID" if ltype == "shared_identifier" else "Stylometry"
                    st.markdown(f"**{label}:** `{data['reliability_pct']}%` reliability ({data['confirmed']}/{data['total']} confirmed)")
            else:
                st.caption("No analyst feedback recorded yet.")
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
# Mandatory disclosure banner (Branch 5) — shown on every screen
# ============================================================

st.warning(f"**Disclosure:** {DISCLOSURE_TEXT}")


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

    # --- Visual Ego Network Graph (Branch 5 / Branch 10) ---
    st.markdown("### 🕸️ Visual Network Graph Explorer")
    render_network_graph(handle)

    st.markdown("---")

    # --- Linked Personas ---
    st.markdown("### 🔗 Linked Personas")

    # --- Multi-Signal Fusion Display ---
    if table_exists("fused_links"):
        fused_df = query_df("""
            SELECT actor_a, actor_b, fused_confidence, contributing_link_types, signal_count, evidence_summary
            FROM fused_links
            WHERE actor_a = ? OR actor_b = ?
            ORDER BY fused_confidence DESC
        """, (handle, handle))

        if not fused_df.empty:
            for _, f_row in fused_df.iterrows():
                other_actor = f_row['actor_b'] if f_row['actor_a'] == handle else f_row['actor_a']
                scount = f_row['signal_count']
                fconf = f_row['fused_confidence']
                types = f_row['contributing_link_types']
                
                if scount > 1:
                    st.success(f"🔥 **Multi-Signal Fused Score: {fconf}%** for **{other_actor}** — Fused across **{scount} independent signals** (`{types}`)")
                else:
                    st.info(f"⚡ **Fused Confidence Score: {fconf}%** for **{other_actor}** (`{types}`)")

    if table_exists("relationship_links"):
        links = query_df("""
            SELECT id, actor_a, actor_b, link_type, evidence, confidence_score
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
                    link_id = link['id']

                    st.markdown(f"""
<div class="link-card link-shared">
    <strong>{other}</strong> &nbsp; {emoji} <span class="{confidence_class(link['confidence_score'])}">Confidence: {link['confidence_score']}%</span><br>
    <span class="evidence-text">📋 {link['evidence']}</span>
</div>
                    """, unsafe_allow_html=True)
                    render_evidence_drawer(link, other, "shared")
                    render_decision_ui(link_id, other, "shared")

            if not style_links.empty:
                st.markdown("#### 🧠 Linked via Writing Style (Semantic Similarity)")
                for _, link in style_links.iterrows():
                    other = link['actor_b'] if link['actor_a'] == handle else link['actor_a']
                    emoji = confidence_emoji(link['confidence_score'])
                    link_id = link['id']

                    st.markdown(f"""
<div class="link-card link-stylometric">
    <strong>{other}</strong> &nbsp; {emoji} <span class="{confidence_class(link['confidence_score'])}">Confidence: {link['confidence_score']}%</span><br>
    <span class="evidence-text">🧠 {link['evidence']}</span><br>
    <span class="evidence-text">⚠️ This pair shares NO PGP key or wallet — semantic similarity only, not authorship proof.</span>
</div>
                    """, unsafe_allow_html=True)
                    render_evidence_drawer(link, other, "style")
                    render_decision_ui(link_id, other, "style")

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
        # Check if this actor is mapped to an infra match via actor_infra_map
        if table_exists("actor_infra_map"):
            infra = query_df("""
                SELECT i.* FROM infra_links i
                JOIN actor_infra_map m ON i.onion_address = m.onion_address
                WHERE m.handle = ?
            """, (handle,))
        else:
            infra = pd.DataFrame()

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
            st.info("No infrastructure correlation matches found for this specific actor.")
    else:
        st.info("Infrastructure links table not found. Run `db_setup.py` first.")

    st.markdown("---")

    # --- Timeline (Branch 6) ---
    st.markdown("### 🕒 Timeline")
    render_timeline(handle)

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

    # --- Visual Network Graph ---
    with st.expander("🕸️ Visual Threat Actor Network Graph (Interactive Node-and-Edge Explorer)", expanded=True):
        render_network_graph()

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
