# frontend/dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date, timedelta
import os
import sys

# Add parent directory to path to import models if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# API CONFIGURATION
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="SATS Roster AI", 
    layout="wide", 
    page_icon="✈️",
    initial_sidebar_state="expanded"
)

# --- THEME MANAGEMENT ---
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'Dark Mode'

def get_theme_css(mode):
    if mode == 'Dark Mode':
        # Dark Theme Palette
        bg_color = "#0f172a"        # Slate 900
        card_bg = "#1e293b"         # Slate 800
        text_color = "#f8fafc"      # Slate 50
        accent_color = "#3b82f6"    # Blue 500
        sidebar_bg = "#002B5B"      # Deep Navy (Requested)
        metric_bg = "#0f172a"       # Darker metric
        border_color = "#334155"    # Slate 700
        success_color = "#10b981"   # Emerald 500
    else:
        # Light Theme Palette
        bg_color = "#f1f5f9"        # Slate 100
        card_bg = "#ffffff"         # White
        text_color = "#0f172a"      # Slate 900
        accent_color = "#002B5B"    # Deep Navy (Brand)
        sidebar_bg = "#ffffff"      # White Sidebar
        metric_bg = "#ffffff"       # White metric
        border_color = "#cbd5e1"    # Slate 300
        success_color = "#059669"   # Emerald 600

    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        color: {text_color};
        background-color: {bg_color};
    }}

    /* Main Background Override */
    .stApp {{
        background-color: {bg_color};
    }}

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: {sidebar_bg};
        border-right: 1px solid {border_color};
    }}
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
        color: {text_color if mode == 'Light Mode' else '#ffffff'};
    }}
    section[data-testid="stSidebar"] .caption {{
        color: {text_color if mode == 'Light Mode' else '#cbd5e1'};
        opacity: 0.8;
    }}

    /* Card/Container Styling */
    div[data-testid="stContainer"] {{
        background-color: {card_bg};
        border-radius: 12px;
        padding: 15px;
        border: 1px solid {border_color};
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    }}

    /* Metrics */
    [data-testid="stMetric"] {{
        background-color: {metric_bg};
        border: 1px solid {border_color};
        padding: 15px;
        border-radius: 10px;
        transition: transform 0.2s;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}
    [data-testid="stMetricLabel"] {{
        color: {text_color};
        opacity: 0.7;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }}
    [data-testid="stMetricValue"] {{
        color: {accent_color};
        font-weight: 700;
        font-size: 1.8rem;
    }}

    /* Buttons */
    .stButton button {{
        border-radius: 6px;
        font-weight: 600;
        border: none;
        transition: all 0.2s;
        background-color: {card_bg};
        color: {text_color};
        border: 1px solid {border_color};
    }}
    .stButton button:hover {{
        border-color: {accent_color};
        color: {accent_color};
    }}
    div[data-testid="stHorizontalBlock"] .stButton button[kind="primary"] {{
        background-color: {accent_color};
        color: #ffffff;
        border: none;
    }}
    div[data-testid="stHorizontalBlock"] .stButton button[kind="primary"]:hover {{
        opacity: 0.9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    /* DataFrame */
    [data-testid="stDataFrame"] {{
        border: 1px solid {border_color};
        border-radius: 8px;
    }}

    /* Status Badges */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .status-online {{ background-color: {success_color}20; color: {success_color}; border: 1px solid {success_color}; }}
    .status-offline {{ background-color: #ef444420; color: #ef4444; border: 1px solid #ef4444; }}

    h1, h2, h3, h4, h5, h6 {{ color: {text_color} !important; font-weight: 700; }}
    .caption {{ color: {text_color} !important; opacity: 0.8; font-size: 0.85rem; }}
    p {{ color: {text_color} !important; }}

    /* Expander */
    .streamlit-expanderHeader {{
        background-color: {card_bg};
        border-radius: 8px;
        color: {text_color};
    }}
</style>
"""

# --- SYSTEM HEALTH ---
server_status = False
try:
    requests.get(f"{API_URL}/", timeout=1)
    server_status = True
except:
    server_status = False

# --- STATE MANAGEMENT ---
DEFAULTS = {
    'shift_config_df': pd.DataFrame([
        {"Name": "Morning Ops", "Start Time": 700, "Duration": 8, "Staff Needed": 2},
        {"Name": "Afternoon Ops", "Start Time": 1500, "Duration": 8, "Staff Needed": 2},
        {"Name": "Night Cargo", "Start Time": 2300, "Duration": 8, "Staff Needed": 1},
    ]),
    'roster_data': None,
    'validation_errors': [],
    'last_metrics': None,
    'staff_db': [],
    'custom_rules': {'max_weekly_hours': 44, 'min_rest_hours': 10},
    'messages': [],
    'roster_state': {"shifts": [], "month_year": None, "location": "Singapore"},
    'use_custom_staff': False
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- HELPER FUNCTIONS ---
def highlight_shifts(val):
    val_str = str(val)
    if 'Night' in val_str: return 'background-color: #553C9A; color: white'
    if 'Morning' in val_str: return 'background-color: #DD6B20; color: white'
    if 'Afternoon' in val_str: return 'background-color: #2B6CB0; color: white'
    if val_str in ['Off']: return 'background-color: #718096; color: white'
    if val_str in ['MC', 'Leave']: return 'background-color: #C53030; color: white'
    return ''

def run_optimization(start_date, days_count, country_enum):
    # Determine Staff Source
    if st.session_state.get('use_custom_staff', False):
        staff_payload = st.session_state.get('staff_db', [])
    else:
        staff_payload = [] # Empty list triggers backend auto-generation

    shifts = []
    config = st.session_state['shift_config_df'].to_dict('records')

    for d in range(days_count):
        curr = start_date + timedelta(days=d)
        curr_str = curr.isoformat()
        for item in config:
            try:
                count = int(item["Staff Needed"])
                # Handle rollover roughly for ID generation
                end_t = (int(item["Start Time"]) + (int(item["Duration"])*100)) % 2400
                for i in range(count):
                    shifts.append({
                        "id": f"{item['Name']}_{d}_{i}",
                        "date": curr_str,
                        "type": item['Name'],
                        "start_time": int(item["Start Time"]),
                        "end_time": end_t,
                        "duration_hours": int(item["Duration"]),
                        "required_staff_count": 1
                    })
            except: continue

    payload = {
        "staff": staff_payload,
        "shifts": shifts,
        "country": country_enum,
        "rules": st.session_state.get('custom_rules')
    }

    try:
        resp = requests.post(f"{API_URL}/optimize", json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            st.session_state['last_metrics'] = result['metrics']
            data = [{"Date": x['date'], "Staff": x['staff_id'], "Shift": x['shift_type']} for x in result['assignments']]
            df = pd.DataFrame(data)
            if not df.empty:
                pivot = df.pivot(index="Staff", columns="Date", values="Shift").fillna("Off")
                st.session_state['roster_data'] = pivot

            # Update Staff List if auto-generated
            if not staff_payload:
                 # Extract unique staff from assignments if we didn't send any
                 unique_staff = sorted(list(set(x['staff_id'] for x in result['assignments'])))
                 # Populate session state just for visualization if needed, but 'roster_data' index is better source
                 pass

            st.session_state['validation_errors'] = []
            return True, "Success"
        return False, f"Optimization Failed: {resp.text}"
    except Exception as e:
        return False, f"API Error: {e}"

def calculate_analytics(roster_df, shift_config_df):
    """
    Calculate hours worked per staff member.
    """
    if roster_df is None or roster_df.empty:
        return None

    # Map shift names to duration
    duration_map = {row['Name']: row['Duration'] for _, row in shift_config_df.iterrows()}

    analytics_data = []
    for staff_id, row in roster_df.iterrows():
        total_hours = 0
        shifts_worked = 0
        for date_col in roster_df.columns:
            shift_name = row[date_col]
            if shift_name in duration_map:
                total_hours += duration_map[shift_name]
                shifts_worked += 1

        analytics_data.append({
            "Staff": staff_id,
            "Total Hours": total_hours,
            "Shifts Worked": shifts_worked
        })

    return pd.DataFrame(analytics_data)

# --- APP LAYOUT ---
COUNTRY_MAP = {"Singapore": "SG", "Malaysia": "MY", "Saudi Arabia": "SA"}

# SIDEBAR NAVIGATION
with st.sidebar:
    st.markdown("### ✈️ SATS Roster AI")
    st.caption("v8.0 | Comprehensive Suite")

    if server_status:
        st.markdown('<div class="status-badge status-online">● System Online</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge status-offline">● Offline</div>', unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio("Navigation", ["📅 Roster Dashboard", "🤖 AI Copilot"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    country_label = st.selectbox("Operating Region", list(COUNTRY_MAP.keys()))
    country_enum = COUNTRY_MAP[country_label]

    theme_mode = st.radio("Display Mode", ["Dark Mode", "Light Mode"], index=0 if st.session_state['theme'] == 'Dark Mode' else 1, horizontal=True)
    if theme_mode != st.session_state['theme']:
        st.session_state['theme'] = theme_mode
        st.rerun()

    # INJECT CSS
    st.markdown(get_theme_css(st.session_state['theme']), unsafe_allow_html=True)
    st.info(f"User: **Planner_{country_enum}**")


# --- PAGE: ROSTER DASHBOARD ---
if page == "📅 Roster Dashboard":
    st.title("Operations Dashboard")
    st.caption("One-stop command center for staffing, scheduling, and compliance.")

    # 1. CONFIGURATION & ACTION BAR
    with st.expander("🛠️ Configuration & Rules", expanded=True):
        c1, c2, c3 = st.columns([1.5, 1.5, 1])

        with c1:
            st.markdown("#### 1. Shift Definitions")
            edited_config = st.data_editor(
                st.session_state['shift_config_df'],
                num_rows="dynamic",
                use_container_width=True,
                key="config_editor_main",
                height=150
            )
            st.session_state['shift_config_df'] = edited_config

        with c2:
            st.markdown("#### 2. Staffing Strategy")
            use_custom = st.toggle("Use Employee Database", value=st.session_state['use_custom_staff'], key='use_custom_staff')
            
            if use_custom:
                st.caption("Upload or edit your staff list.")
                uc1, uc2 = st.columns([3, 1])
                uploaded_file = uc1.file_uploader("Import CSV", type=["csv"], label_visibility="collapsed")
                if uc2.button("Clear DB"): st.session_state['staff_db'] = []

                if uploaded_file:
                    try:
                        df = pd.read_csv(uploaded_file)
                        df.columns = [c.lower() for c in df.columns]
                        st.session_state['staff_db'] = df.to_dict('records')
                        st.toast("Staff Imported Successfully")
                    except Exception as e: st.error(str(e))

                staff_df = pd.DataFrame(st.session_state['staff_db'])
                edited_staff = st.data_editor(staff_df, num_rows="dynamic", use_container_width=True, height=100)
                st.session_state['staff_db'] = edited_staff.to_dict('records')
            else:
                st.info("✨ **Auto-Pilot Mode**: The system will automatically calculate the required headcount and generate 'Open Position' assignments based on shift overlap.")

        with c3:
            st.markdown("#### 3. Execution")
            today = date.today()
            dr = st.date_input("Roster Period", value=(today, today + timedelta(days=6)), min_value=today)

            days_count = 7
            start_date = today
            if len(dr) == 2:
                days_count = (dr[1] - dr[0]).days + 1
                start_date = dr[0]

            if st.button("🚀 Generate Roster", type="primary", use_container_width=True):
                with st.spinner("Optimizing schedule..."):
                    success, msg = run_optimization(start_date, days_count, country_enum)
                    if success: st.success("Optimization Complete!")
                    else: st.error(msg)

            with st.popover("Advanced Constraints"):
                mh = st.number_input("Max Weekly Hours", 40, 60, 44)
                mr = st.number_input("Min Rest (Hours)", 8, 24, 10)
                st.session_state['custom_rules'] = {'max_weekly_hours': mh, 'min_rest_hours': mr}

    # 2. ANALYTICS & RESULTS
    if st.session_state['roster_data'] is not None:
        st.markdown("---")
        
        # METRICS ROW
        m1, m2, m3, m4 = st.columns(4)
        
        # Calculate Analytics
        analytics_df = calculate_analytics(st.session_state['roster_data'], st.session_state['shift_config_df'])
        
        # Overall Stats
        total_hours = analytics_df['Total Hours'].sum() if analytics_df is not None else 0
        avg_hours = analytics_df['Total Hours'].mean() if analytics_df is not None else 0
        fairness_std = analytics_df['Total Hours'].std() if analytics_df is not None else 0

        m1.metric("Total Man-Hours", f"{total_hours}h")
        m2.metric("Avg Hours / Staff", f"{avg_hours:.1f}h")
        m3.metric("Fairness (StdDev)", f"{fairness_std:.1f}", help="Lower is better (more equal distribution)")

        if st.session_state.get('last_metrics'):
            m = st.session_state['last_metrics']
            m4.metric("Solver Speed", f"{m.get('runtime_seconds', 0)}s")

        # MAIN SPLIT
        left_p, right_p = st.columns([2, 1])

        with left_p:
            st.subheader("🗓️ Interactive Schedule")

            # Toolbar
            tb1, tb2 = st.columns([1, 1])
            with tb2:
                csv = st.session_state['roster_data'].to_csv().encode('utf-8')
                st.download_button("📥 Export to CSV", csv, "roster.csv", "text/csv", use_container_width=True)

            # The Table
            display_df = st.session_state['roster_data'].copy()
            st.dataframe(
                display_df.style.map(highlight_shifts),
                use_container_width=True,
                height=500
            )

        with right_p:
            st.subheader("📊 Analytics & Fairness")
            
            if analytics_df is not None:
                # 1. Hours Distribution Chart
                fig_bar = px.bar(
                    analytics_df,
                    x='Total Hours',
                    y='Staff',
                    orientation='h',
                    title="Hours Worked per Staff",
                    template="plotly_dark" if st.session_state['theme'] == 'Dark Mode' else "plotly_white",
                    color="Total Hours",
                    color_continuous_scale="Viridis"
                )
                fig_bar.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_bar, use_container_width=True)

            # Compliance Section
            st.markdown("### 🛡️ Compliance Audit")
            if st.button("Run Full Compliance Check", use_container_width=True):
                 with st.spinner("Auditing against labor laws..."):
                    # Prepare payload
                    user_assignments = []
                    for staff_id, row in st.session_state['roster_data'].iterrows():
                        for date_str, shift_val in row.items():
                            user_assignments.append({'staff_id': staff_id, 'date': date_str, 'shift': shift_val})

                    payload = {
                        "assignments": user_assignments,
                        "shift_definitions": st.session_state['shift_config_df'].to_dict('records'),
                        "country": country_enum
                    }
                    try:
                        r = requests.post(f"{API_URL}/validate", json=payload, timeout=15)
                        if r.status_code == 200:
                            st.session_state['audit_result'] = r.json()
                            st.toast("Audit Complete")
                        else: st.error("Audit Failed")
                    except Exception as e: st.error(str(e))
            
            # Display Audit Results
            if 'audit_result' in st.session_state:
                res = st.session_state['audit_result']
                audit = res.get('compliance_audit', {})
                tech = res.get('technical_errors', [])
                
                if tech:
                    st.error(f"{len(tech)} Technical Conflicts")

                if audit:
                    verdict = audit.get('verdict', 'UNKNOWN')
                    color = "green" if verdict == "PASS" else "red"
                    st.markdown(f"**Verdict:** :{color}[{verdict}]")
                    st.caption(audit.get('summary', ''))

                    if audit.get('violations'):
                        with st.expander("View Violations"):
                             for v in audit['violations']:
                                 st.markdown(f"- **{v['type']}**: {v['description']}")

# --- PAGE: AI ASSISTANT ---
elif page == "🤖 AI Copilot":
    st.title("AI Roster Analyst")
    st.caption("Ask questions about labor laws, request changes, or analyze fairness.")

    cl, cr = st.columns([2, 1])

    with cl:
        chat_cont = st.container(height=600)
        for msg in st.session_state.messages:
            chat_cont.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Ask me anything..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            chat_cont.chat_message("user").write(prompt)

            try:
                # Sync state
                payload = {"message": prompt, "state": st.session_state.roster_state}
                r = requests.post(f"{API_URL}/agent/chat", json=payload, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    bot_reply = data.get('reply')
                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                    chat_cont.chat_message("assistant").write(bot_reply)

                    if data.get('action') == "GENERATE":
                        st.toast("AI Triggered Optimization...")
                        run_optimization(date.today(), 7, country_enum)
            except Exception as e:
                chat_cont.error(f"AI Error: {e}")

    with cr:
        st.markdown("### 📚 Legal Knowledge Base")
        st.info(f"Active Jurisdiction: **{country_label}**")
        kq = st.text_input("Search Specific Regulation")
        if kq:
            try:
                r = requests.get(f"{API_URL}/compliance/search", params={"query": kq, "country": country_enum})
                if r.status_code == 200:
                    for item in r.json():
                         with st.container():
                             st.markdown(f"**{item.get('law_name', 'Regulation')}**")
                             st.caption(item.get('text', '')[:300] + "...")
                             st.markdown("---")
            except: pass
