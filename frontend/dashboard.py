# frontend/dashboard.py
import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
from datetime import date, timedelta
import calendar
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
    initial_sidebar_state="collapsed"
)

# --- MODERN ENTERPRISE THEME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #E2E8F0;
    }

    /* CARD STYLING */
    div[data-testid="stContainer"] {
        background-color: #1A202C; /* darker bg */
        border-radius: 12px;
        padding: 10px;
    }

    /* CUSTOM METRICS */
    [data-testid="stMetric"] {
        background-color: #2D3748;
        border: 1px solid #4A5568;
        padding: 20px;
        border-radius: 10px;
        transition: transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    [data-testid="stMetricLabel"] { color: #A0AEC0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="stMetricValue"] { color: #F7FAFC; font-weight: 700; font-size: 1.8rem; }

    /* BUTTONS */
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        border: none;
        transition: all 0.2s;
    }
    div[data-testid="stHorizontalBlock"] .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #3182CE 0%, #2B6CB0 100%);
        box-shadow: 0 4px 6px rgba(49, 130, 206, 0.3);
    }
    div[data-testid="stHorizontalBlock"] .stButton button[kind="primary"]:hover {
        box-shadow: 0 6px 8px rgba(49, 130, 206, 0.4);
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
        border-bottom: 1px solid #4A5568;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 4px 4px 0 0;
        color: #A0AEC0;
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #63B3ED;
        border-bottom: 2px solid #63B3ED;
    }

    /* DATAFRAME */
    [data-testid="stDataFrame"] {
        border: 1px solid #2D3748;
        border-radius: 8px;
    }

    /* ALERTS & STATUS */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .status-online { background: rgba(5, 150, 105, 0.2); color: #34D399; border: 1px solid #059669; }
    .status-offline { background: rgba(220, 38, 38, 0.2); color: #F87171; border: 1px solid #B91C1C; }

    h1, h2, h3 { color: #F7FAFC; }
    .caption { color: #718096; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

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
    'staff_db': [
        {"id": "S1", "name": "Ali", "role": "Driver", "country": "Singapore"},
        {"id": "S2", "name": "Bob", "role": "Loader", "country": "Singapore"},
        {"id": "S3", "name": "Charlie", "role": "Supervisor", "country": "Singapore"},
        {"id": "S4", "name": "David", "role": "Driver", "country": "Singapore"},
    ],
    'custom_rules': {'max_weekly_hours': 44, 'min_rest_hours': 10},
    'messages': [],
    'roster_state': {"shifts": [], "month_year": None, "location": "Singapore"}
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- HELPER FUNCTIONS ---
def highlight_shifts(val):
    val_str = str(val)
    if 'Night' in val_str: return 'background-color: #553C9A; color: white' # Purple
    if 'Morning' in val_str: return 'background-color: #DD6B20; color: white' # Orange
    if 'Afternoon' in val_str: return 'background-color: #2B6CB0; color: white' # Blue
    if val_str in ['Off']: return 'background-color: #1A202C; color: #4A5568' # Dark Grey
    if val_str in ['MC', 'Leave']: return 'background-color: #C53030; color: white' # Red
    return ''

def run_forecast(days_count, buffer_pct, country_enum):
    clean_inputs = st.session_state['shift_config_df'].to_dict('records')
    payload = {
        "shift_inputs": clean_inputs,
        "days": days_count,
        "country": country_enum,
        "buffer": buffer_pct
    }
    try:
        resp = requests.post(f"{API_URL}/forecast", json=payload, timeout=10)
        if resp.status_code == 200:
            res = resp.json()
            st.session_state['forecast_res'] = res
            return True, res
        return False, f"Forecast Failed: {resp.text}"
    except Exception as e:
        return False, str(e)

def run_optimization(start_date, days_count, country_enum):
    staff_payload = st.session_state['staff_db']
    shifts = []
    config = st.session_state['shift_config_df'].to_dict('records')

    for d in range(days_count):
        curr = start_date + timedelta(days=d)
        curr_str = curr.isoformat()
        for item in config:
            try:
                count = int(item["Staff Needed"])
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
            st.session_state['last_staff_list'] = staff_payload
            st.session_state['validation_errors'] = []
            return True, "Success"
        return False, f"Optimization Failed: {resp.text}"
    except Exception as e:
        return False, f"API Error: {e}"

# --- APP LAYOUT ---
COUNTRY_MAP = {"Singapore": "SG", "Malaysia": "MY", "Saudi Arabia": "SA"}

with st.sidebar:
    st.markdown("### ✈️ SATS Roster AI")
    st.caption("v6.0 | Enterprise Edition")

    if server_status:
        st.markdown('<div class="status-badge status-online">● System Online</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge status-offline">● Offline</div>', unsafe_allow_html=True)
        st.error("Check backend connection")

    st.markdown("---")
    country_label = st.selectbox("Operating Region", list(COUNTRY_MAP.keys()))
    country_enum = COUNTRY_MAP[country_label]

    st.markdown("---")
    st.info(f"Logged in as: **Planner_{country_enum}**")

# --- MAIN NAVIGATION ---
tabs = st.tabs(["🏗️ Setup & Resources", "📈 Demand Planning", "⚙️ Roster Engine", "🎮 Operations Center", "🧠 AI Analyst"])

# TAB 1: SETUP & RESOURCES
with tabs[0]:
    st.markdown("## Resource Configuration")
    st.caption("Manage master data: Shift Definitions and Employee Database.")
    
    c1, c2 = st.columns([1, 1.2])
    
    with c1:
        with st.container(border=True):
            st.markdown("### 🕒 Shift Definitions")
            st.caption("Define standard shift patterns and default staffing requirements.")
            edited_config = st.data_editor(
                st.session_state['shift_config_df'],
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Name": st.column_config.TextColumn("Shift Name", required=True),
                    "Start Time": st.column_config.NumberColumn("Start (2400)", format="%d"),
                    "Duration": st.column_config.NumberColumn("Duration (Hrs)"),
                    "Staff Needed": st.column_config.NumberColumn("Headcount")
                },
                key="config_editor_main"
            )
            st.session_state['shift_config_df'] = edited_config

    with c2:
        with st.container(border=True):
            st.markdown("### 👥 Employee Database")
            st.caption("Manage active staff list.")
            
            # Simple controls
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
            edited_staff = st.data_editor(
                staff_df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "id": "ID", "name": "Name",
                    "role": st.column_config.SelectboxColumn("Role", options=["Driver", "Loader", "Supervisor"]),
                    "country": st.column_config.SelectboxColumn("Region", options=list(COUNTRY_MAP.keys()))
                },
                key="staff_editor_main",
                height=300
            )
            st.session_state['staff_db'] = edited_staff.to_dict('records')
            st.caption(f"Total Active Staff: {len(st.session_state['staff_db'])}")

# TAB 2: DEMAND PLANNING
with tabs[1]:
    st.markdown("## Demand Forecasting")
    st.caption("Simulate staffing needs based on flight schedules and absenteeism models.")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        today = date.today()

        with c1:
            dr = st.date_input("Simulation Period", value=(today, today + timedelta(days=6)), min_value=today)
            if len(dr) == 2:
                days_count = (dr[1] - dr[0]).days + 1
                st.session_state['cal_start'] = dr[0]
                st.session_state['cal_days'] = days_count
            else: days_count = 0

        with c2:
            buf = st.slider("Absenteeism Buffer (%)", 0, 30, 15)

        with c3:
            st.write("") # Spacer
            st.write("")
            if st.button("▶ Run Simulation", type="primary", use_container_width=True):
                if days_count > 0:
                    with st.spinner("Simulating..."):
                        run_forecast(days_count, buf/100.0, country_enum)
    
    if 'forecast_res' in st.session_state:
        res = st.session_state['forecast_res']
        st.markdown("### Simulation Results")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Minimum Staff", res['min_staff'])
        m2.metric("Recommended Safe", res['rec_staff'], delta=f"+{res['buffer_size']} Buffer")
        
        real_count = len(st.session_state.get('staff_db', []))
        gap = res['rec_staff'] - real_count
        
        if gap > 0:
            m3.metric("Staffing Gap", f"-{gap}", delta_color="inverse")
            st.warning(f"Shortage Detected: You need {gap} more staff for safe operations.")
            if st.button(f"🛠️ Auto-Hire {gap} Temp Staff"):
                # Logic to add temp staff
                base = len(st.session_state['staff_db'])
                new_staff = [{"id": f"T{base+i}", "name": f"Temp_{i}", "role": "Driver", "country": country_label} for i in range(gap)]
                st.session_state['staff_db'].extend(new_staff)
                st.rerun()
        else:
            m3.metric("Staffing Gap", "0", delta_color="normal")
            st.success("Staffing levels are sufficient.")

# TAB 3: ROSTER ENGINE
with tabs[2]:
    st.markdown("## Optimization Engine")
    st.caption("Configure constraints and generate the roster.")

    c_ctrl, c_rules = st.columns([1, 2])

    with c_ctrl:
        st.info(f"Target: **{st.session_state.get('cal_days', 7)} Days** starting **{st.session_state.get('cal_start', date.today())}**")

        if st.button("🚀 Launch Optimizer", type="primary", use_container_width=True):
            with st.status("Optimizing...", expanded=True) as status:
                st.write("Initializing Solver...")
                s_date = st.session_state.get('cal_start', date.today())
                n_days = st.session_state.get('cal_days', 7)

                success, msg = run_optimization(s_date, n_days, country_enum)
                if success:
                    status.update(label="Optimization Complete!", state="complete", expanded=False)
                    st.toast("Roster Generated Successfully")
                else:
                    status.update(label="Optimization Failed", state="error")
                    st.error(msg)

    with c_rules:
        with st.expander("⚙️ Advanced Policy Constraints", expanded=True):
            rc1, rc2 = st.columns(2)
            mh = rc1.number_input("Max Weekly Hours", 40, 60, 44)
            mr = rc2.number_input("Min Rest (Hours)", 8, 24, 10)
            st.session_state['custom_rules'] = {'max_weekly_hours': mh, 'min_rest_hours': mr}
            st.caption(f"Active Profile: {country_enum} Labor Laws Override")

# TAB 4: OPERATIONS CENTER
with tabs[3]:
    if st.session_state['roster_data'] is None:
        st.warning("No Roster Available. Please generate one in the 'Roster Engine' tab.")
    else:
        # METRICS HEADER
        if st.session_state.get('last_metrics'):
            m = st.session_state['last_metrics']
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Solution Time", f"{m['runtime_seconds']}s")
            c2.metric("Fairness Score", m['fairness_gap'])
            c3.metric("Total Shifts", m['shift_count'])
            c4.metric("Assignments", "OPTIMAL")

        st.markdown("---")

        # MAIN WORKSPACE SPLIT
        left_panel, right_panel = st.columns([2.5, 1])

        with left_panel:
            st.subheader("🗓️ Operational Roster")

            # Toolbar
            tb1, tb2 = st.columns([1, 1])
            with tb1:
                # View Mode logic could go here
                pass
            with tb2:
                csv = st.session_state['roster_data'].to_csv().encode('utf-8')
                st.download_button("📥 Export CSV", csv, "roster.csv", "text/csv", use_container_width=True)

            # The Table
            display_df = st.session_state['roster_data'].copy()
            # Clean dates
            cols = []
            for c in display_df.columns:
                try: cols.append(date.fromisoformat(c).strftime("%d/%m"))
                except: cols.append(c)
            display_df.columns = cols
            
            st.dataframe(
                display_df.style.map(highlight_shifts),
                use_container_width=True,
                height=500
            )
            
            # Quick Editor
            with st.expander("✏️ Quick Shift Editor"):
                staff_list = st.session_state['roster_data'].index.tolist()
                s_staff = st.selectbox("Staff", staff_list)
                if s_staff:
                    row = st.session_state['roster_data'].loc[s_staff]
                    s_date = st.selectbox("Date", row.index)
                    current_shift = row[s_date]
                    new_shift = st.selectbox("Assign Shift", ["Off", "Leave", "MC", "Morning Ops", "Afternoon Ops", "Night Cargo"], index=0)
                    if st.button("Apply Change"):
                        st.session_state['roster_data'].at[s_staff, s_date] = new_shift
                        st.toast("Shift Updated")
                        st.rerun()

        with right_panel:
            st.subheader("🛡️ Compliance Audit")
            
            if st.button("🔍 Run Full Audit", type="primary", use_container_width=True):
                with st.spinner("Auditing against laws..."):
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
            
            # DISPLAY RESULTS
            if 'audit_result' in st.session_state:
                res = st.session_state['audit_result']
                audit = res.get('compliance_audit', {})
                tech = res.get('technical_errors', [])
                
                # Tech Errors
                if tech:
                    st.error(f"{len(tech)} Critical Constraints Broken")
                    for t in tech[:3]:
                        st.markdown(f"**{t['type']}**: {t['msg']}")
                else:
                    st.success("Technical Constraints Met")

                st.markdown("---")

                # AI Compliance
                if audit:
                    verdict = audit.get('verdict', 'UNKNOWN')
                    color = "green" if verdict == "PASS" else "red"
                    st.markdown(f"### AI Verdict: :{color}[{verdict}]")
                    st.info(audit.get('summary', 'No summary available.'))

                    if audit.get('violations'):
                        st.markdown("#### Violations")
                        for v in audit['violations']:
                            with st.container(border=True):
                                st.markdown(f"**{v['type']}**")
                                st.caption(v['description'])
                                st.markdown(f"*Ref: {v['legal_citation']}*")
                    else:
                        st.caption("No regulatory violations found.")

# TAB 5: AI ANALYST
with tabs[4]:
    st.markdown("## 🧠 AI Copilot")
    st.caption("Chat with your roster data. Ask about laws, optimization, or specific staff schedules.")

    cl, cr = st.columns([2, 1])

    with cl:
        # Chat Interface
        chat_cont = st.container(height=500)
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

                    # Handle Actions
                    if data.get('action') == "GENERATE":
                        st.toast("AI Triggered Optimization...")
                        run_optimization(date.today(), 7, country_enum)
                        st.rerun()
            except Exception as e:
                chat_cont.error(f"AI Error: {e}")

    with cr:
        # Knowledge Search
        st.markdown("### 📚 Legal Knowledge")
        kq = st.text_input("Search Regulations")
        if kq:
            try:
                r = requests.get(f"{API_URL}/compliance/search", params={"query": kq, "country": country_enum})
                if r.status_code == 200:
                    for item in r.json():
                         with st.container(border=True):
                             st.markdown(item)
            except: pass
