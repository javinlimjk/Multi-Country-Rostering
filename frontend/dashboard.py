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
# We define simple classes here to avoid import errors if models.py is missing in frontend container
class Country:
    SINGAPORE = "SG"
    MALAYSIA = "MY"
    SAUDI_ARABIA = "SA"

# API CONFIGURATION
# If running in Docker, this might need to be "http://backend:8000"
# For local dev, "http://127.0.0.1:8000" is fine.
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="SATS Roster AI", 
    layout="wide", 
    page_icon="✈️",
    initial_sidebar_state="expanded"
)

# --- ENTERPRISE CSS THEME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* METRIC CARDS */
    [data-testid="stMetric"] {
        background-color: #1E252B; /* Dark Navy */
        border: 1px solid #2E3B4E;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    [data-testid="stMetricLabel"] { color: #A0AEC0; font-size: 0.9rem; }
    [data-testid="stMetricValue"] { color: #FFFFFF; font-weight: 700; }

    /* BUTTON STYLING */
    .stButton button {
        border-radius: 6px;
        font-weight: 600;
        border: none;
        width: 100%;
        transition: all 0.2s ease;
    }
    div[data-testid="stHorizontalBlock"] .stButton button[kind="primary"] {
        background-color: #D32F2F; 
        color: white;
    }

    /* TABLE STYLING */
    [data-testid="stDataFrame"] {
        border: 1px solid #2E3B4E;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* STATUS INDICATOR */
    .status-pill {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-online { background-color: #064E3B; color: #34D399; border: 1px solid #059669; }
    .status-offline { background-color: #450A0A; color: #F87171; border: 1px solid #B91C1C; }
</style>
""", unsafe_allow_html=True)

# --- SYSTEM HEALTH CHECK ---
server_status = False
try:
    requests.get(f"{API_URL}/", timeout=1)
    server_status = True
except:
    server_status = False

# --- INIT STATE ---
if 'shift_config_df' not in st.session_state:
    st.session_state['shift_config_df'] = pd.DataFrame([
        {"Name": "Morning Ops", "Start Time": 700, "Duration": 8, "Staff Needed": 2},
        {"Name": "Afternoon Ops", "Start Time": 1500, "Duration": 8, "Staff Needed": 2},
        {"Name": "Night Cargo", "Start Time": 2300, "Duration": 8, "Staff Needed": 1},
    ])

if 'roster_data' not in st.session_state: st.session_state['roster_data'] = None
if 'validation_errors' not in st.session_state: st.session_state['validation_errors'] = []
if 'last_metrics' not in st.session_state: st.session_state['last_metrics'] = None

# Init Staff DB if empty
if 'staff_db' not in st.session_state:
    st.session_state['staff_db'] = [
        {"id": "S1", "name": "Ali", "role": "Driver", "country": "Singapore"},
        {"id": "S2", "name": "Bob", "role": "Loader", "country": "Singapore"},
        {"id": "S3", "name": "Charlie", "role": "Supervisor", "country": "Singapore"},
        {"id": "S4", "name": "David", "role": "Driver", "country": "Singapore"},
    ]

current_shifts = st.session_state['shift_config_df'].to_dict('records')
shift_options = [s['Name'] for s in current_shifts] + ["Off", "Leave", "MC"]

# --- HELPER: COLOR MAP ---
def highlight_shifts(val):
    color = ''
    val_str = str(val)
    if 'Night' in val_str: color = 'background-color: #4a148c; color: white'
    elif 'Morning' in val_str: color = 'background-color: #e65100; color: white'
    elif 'Afternoon' in val_str: color = 'background-color: #01579b; color: white'
    elif val_str in ['Off']: color = 'background-color: #263238; color: grey'
    elif val_str in ['MC', 'Leave']: color = 'background-color: #b71c1c; color: white'
    return color

# --- HELPER: METRIC REFRESH ---
def refresh_metrics():
    if st.session_state['roster_data'] is not None:
        user_assignments = []
        for staff_id, row in st.session_state['roster_data'].iterrows():
            for date_col, shift_val in row.items():
                user_assignments.append({'staff_id': staff_id, 'date': str(date_col), 'shift': shift_val})
        try:
            resp = requests.post(f"{API_URL}/metrics", json={"assignments": user_assignments})
            if resp.status_code == 200:
                st.session_state['last_metrics'] = resp.json()
        except: pass

COUNTRY_MAP = {
    "Singapore": "SG",
    "Malaysia": "MY",
    "Saudi Arabia": "SA"
}

# --- SIDEBAR ---
with st.sidebar:
    st.title("✈️ SATS Roster AI")
    st.caption("v6.0 | Production Ready")
    st.divider()
    if server_status:
        st.markdown('<span class="status-pill status-online">● System Online</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill status-offline">● Backend Offline</span>', unsafe_allow_html=True)
        st.error("Ensure backend is running on port 8000")
    st.divider()
    country_label = st.selectbox("Region", list(COUNTRY_MAP.keys()))
    country_enum = COUNTRY_MAP[country_label] 
    st.info(f"User: **Planner_Admin ({country_enum})**")

# --- MAIN WORKSPACE ---
tab_config, tab_staff, tab_ops, tab_legal = st.tabs(["⚙️ Configuration", "👥 Staff Management", "🗓️ Roster Ops", "⚖️ Compliance"])

# =========================================================
# TAB 1: CONFIGURATION
# =========================================================
with tab_config:
    st.header("Operational Planning")
    
    col_editor, col_sim = st.columns([1.5, 1])
    
    # 1. SHIFT EDITOR
    with col_editor:
        st.subheader("1. Define Shift Patterns")
        edited_config = st.data_editor(
            st.session_state['shift_config_df'],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Name": st.column_config.TextColumn("Shift Name", required=True),
                "Start Time": st.column_config.NumberColumn("Start (2400)", min_value=0, max_value=2359, step=100),
                "Duration": st.column_config.NumberColumn("Duration", min_value=4, max_value=12, format="%d hrs"),
                "Staff Needed": st.column_config.NumberColumn("Headcount", min_value=1, max_value=50, step=1)
            },
            key="config_editor" 
        )
        st.session_state['shift_config_df'] = edited_config

        # --- ADVANCED POLICY EXPANDER (NEW) ---
        with st.expander("⚙️ Advanced Policy Configuration"):
            st.caption("Override default labor rules for this run.")
            c1, c2 = st.columns(2)
            max_hours = c1.number_input("Max Weekly Hours", value=44)
            min_rest = c2.number_input("Min Rest Duration (Hours)", value=10)
            
            st.info(f"Current Profile: {country_label} ({max_hours}h work week, {min_rest}h rest)")
            # Store these to send with payload later
            st.session_state['custom_rules'] = {'max_weekly_hours': max_hours, 'min_rest_hours': min_rest}

    # 2. AI SIMULATION
    with col_sim:
        st.subheader("2. AI Forecasting")
        with st.container(border=True):
            
            # DATE RANGE
            c_date, c_buf = st.columns(2)
            today = date.today()
            default_end = today + timedelta(days=6)
            
            date_range = c_date.date_input("Select Period", value=(today, default_end), min_value=today)
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                days_count = (end_date - start_date).days + 1
                st.session_state['cal_start'] = start_date
                st.session_state['cal_days'] = days_count
                c_buf.metric("Duration", f"{days_count} Days")
            else:
                st.session_state['cal_days'] = 0
                c_buf.warning("Select End Date")
            
            buffer_pct = st.slider("Absenteeism Buffer", 0, 30, 15, format="%d%%")
            
            if st.button("🧮 Calculate Requirements", type="primary", disabled=not server_status):
                if st.session_state['cal_days'] == 0:
                    st.error("Invalid Date Range")
                else:
                    clean_inputs = st.session_state['shift_config_df'].to_dict('records')
                    payload = {
                        "shift_inputs": clean_inputs, 
                        "days": st.session_state['cal_days'],
                        "country": country_enum, 
                        "buffer": buffer_pct / 100.0
                    }
                    with st.spinner("Running Monte Carlo Simulation..."):
                        try:
                            resp = requests.post(f"{API_URL}/forecast", json=payload)
                            if resp.status_code == 200:
                                res = resp.json()
                                st.session_state['forecast_res'] = res
                                st.toast("Calculation Complete", icon="✅")
                            else: st.error(f"Forecast Failed: {resp.text}")
                        except Exception as e: st.error(f"Connection Error: {e}")

            # 3. RESULTS
            if 'forecast_res' in st.session_state:
                res = st.session_state['forecast_res']
                st.divider()
                m1, m2 = st.columns(2)
                m1.metric("Minimum Required", f"{res['min_staff']} Staff")
                m2.metric("Recommended (Safe)", f"{res['rec_staff']} Staff", delta=f"+{res['buffer_size']} Buffer")
                
                with st.container(border=True):
                    st.markdown("#### 3. Strategic Gap Analysis")
                    
                    real_staff = st.session_state.get('staff_db', [])
                    real_count = len(real_staff)
                    
                    # 1. Visual Progress Bar & Status Message
                    if real_count >= res['rec_staff']:
                        bar_color = "green"
                        msg = "✅ **Healthy Staffing:** You have enough staff for robust operations."
                    elif real_count >= res['min_staff']:
                        bar_color = "orange"
                        msg = f"⚠️ **High Risk:** You meet the minimum ({res['min_staff']}), but have no buffer for sickness."
                    else:
                        bar_color = "red"
                        msg = f"🛑 **Critical Shortage:** You are missing **{res['min_staff'] - real_count}** staff. Optimization will likely fail."

                    st.markdown(msg)
                    # Progress bar capped at 1.0 (100%)
                    st.progress(min(1.0, real_count / res['rec_staff']) if res['rec_staff'] > 0 else 0)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Current Headcount", real_count)
                    c2.metric("Gap to Minimum", f"{max(0, res['min_staff'] - real_count)}")
                    c3.metric("Gap to Safe", f"{max(0, res['rec_staff'] - real_count)}")

                    # 2. The "Bridge" Feature (Auto-Hire)
                    if real_count < res['rec_staff']:
                        st.divider()
                        st.caption("🛠️ **Simulation Options**")
                        
                        gap = res['rec_staff'] - real_count
                        if st.button(f"➕ Auto-Hire {gap} Temp Staff (Simulation)"):
                            # Generate Dummy Staff to fill the gap
                            # Find the highest existing ID (e.g., S33) to increment correctly
                            existing_ids = [int(x['id'][1:]) for x in real_staff if x['id'].startswith('S') and x['id'][1:].isdigit()]
                            base_id = max(existing_ids) if existing_ids else 0
                            
                            new_staff = []
                            for i in range(gap):
                                new_id = f"S{base_id + i + 1}"
                                new_staff.append({
                                    "id": new_id, 
                                    "name": f"Temp_Staff_{i+1}", 
                                    "role": "Driver", # Default role
                                    "country": country_label
                                })
                            
                            # Update Session State and Rerun to refresh UI
                            st.session_state['staff_db'].extend(new_staff)
                            st.rerun()

                    st.divider()
                    
                    # 3. Generate Button (Protected)
                    # Disable if below ABSOLUTE minimum to prevent solver crash
                    is_disabled = real_count < res['min_staff']
                    
                    if st.button("🚀 Generate Roster", type="primary", disabled=(not server_status or is_disabled)):
                        if is_disabled:
                            st.error("Cannot generate: Staff count is below mathematical minimum.")
                        else:
                            with st.spinner("Generating Assignments..."):
                                # USE REAL STAFF FROM DB
                                staff_payload = st.session_state['staff_db']
                                
                                shifts = []
                                gen_start = st.session_state.get('cal_start', date.today())
                                gen_days = st.session_state.get('cal_days', 7)
                                config = st.session_state['shift_config_df'].to_dict('records')
                                
                                for d in range(gen_days):
                                    curr = gen_start + timedelta(days=d)
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
                                    resp = requests.post(f"{API_URL}/optimize", json=payload)
                                    if resp.status_code == 200:
                                        result = resp.json()
                                        st.session_state['last_metrics'] = result['metrics']
                                        
                                        data = [{"Date": x['date'], "Staff": x['staff_id'], "Shift": x['shift_type']} for x in result['assignments']]
                                        df = pd.DataFrame(data)
                                        pivot = df.pivot(index="Staff", columns="Date", values="Shift").fillna("Off")
                                        
                                        st.session_state['roster_data'] = pivot
                                        st.session_state['last_staff_list'] = staff_payload
                                        st.session_state['validation_errors'] = []
                                        st.toast("Roster Generated!", icon="🚀")
                                    else: st.error(f"Optimization Failed: {resp.text}")
                                except Exception as e: st.error(f"API Error: {e}")
# =========================================================
# TAB 2: STAFF MANAGEMENT (NEW)
# =========================================================
with tab_staff:
    st.header("👥 Staff Database")
    st.caption("Manage your workforce here. These are the people who will be scheduled.")
    
    col_up, col_db = st.columns([1, 2])
    
    with col_up:
        st.markdown("### Import Data")
        uploaded_file = st.file_uploader("Upload CSV (Columns: id, name, role, country)", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                # Normalize headers
                df.columns = [c.lower() for c in df.columns]
                required = {'id', 'name', 'role', 'country'}
                if required.issubset(df.columns):
                    st.session_state['staff_db'] = df.to_dict('records')
                    st.success(f"✅ Loaded {len(df)} staff members.")
                else:
                    st.error(f"CSV missing columns. Needs: {required}")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
        
        st.markdown("---")
        if st.button("🗑️ Clear Database"):
            st.session_state['staff_db'] = []
            st.rerun()

    with col_db:
        st.markdown("### Live Editor")
        if 'staff_db' not in st.session_state: st.session_state['staff_db'] = []
        
        # Convert list of dicts to DF for editor
        staff_df = pd.DataFrame(st.session_state['staff_db'])
        
        edited_staff = st.data_editor(
            staff_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "id": st.column_config.TextColumn("Staff ID", required=True),
                "name": st.column_config.TextColumn("Full Name"),
                "role": st.column_config.SelectboxColumn("Role", options=["Driver", "Loader", "Supervisor"]),
                "country": st.column_config.SelectboxColumn("Base", options=["Singapore", "Malaysia", "Saudi Arabia"])
            },
            key="staff_editor"
        )
        # Save back to session state on change
        st.session_state['staff_db'] = edited_staff.to_dict('records')

# =========================================================
# TAB 3: ROSTER OPS
# =========================================================
with tab_ops:
    if st.session_state['roster_data'] is None:
        st.info("⚠️ Please generate a roster in the 'Configuration' tab first.")
    else:
        # --- METRICS ---
        if st.session_state['last_metrics']:
            met = st.session_state['last_metrics']
            st.markdown("### ⚡ System Performance")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Solver Runtime", f"{met['runtime_seconds']}s")
            c2.metric("Fairness Gap", f"{met['fairness_gap']}", help="Difference between most and least worked staff")
            c3.metric("Total Shifts", met['shift_count'])
            c4.metric("Status", met['status'])
            st.divider()

        # --- VISUALS ---
        st.header("Workforce Analytics")
        roster_long = st.session_state['roster_data'].reset_index().melt(id_vars="Staff", var_name="Date", value_name="Shift")
        workload_df = roster_long[~roster_long['Shift'].isin(['Off', 'Leave', 'MC'])]
        shift_counts = workload_df.groupby("Staff").size().reset_index(name="Shifts")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("📊 Fairness (Total Workload)")
            if not shift_counts.empty:
                fig_load = px.bar(shift_counts, x="Staff", y="Shifts", color="Shifts", color_continuous_scale="Reds")
                fig_load.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_load, use_container_width=True)
        with c2:
            st.subheader("🌙 Shift Distribution")
            if not workload_df.empty:
                fig_type = px.histogram(workload_df, x="Staff", color="Shift", barmode="stack")
                fig_type.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_type, use_container_width=True)

        st.divider()

        # --- ROSTER TABLE ---
        st.header("Roster Operations Dashboard")
        with st.expander("👁️ Full Schedule Overview (Read-Only)", expanded=True):
            display_df = st.session_state['roster_data'].copy()
            new_cols = []
            for date_str in display_df.columns:
                try:
                    d = date.fromisoformat(date_str)
                    new_cols.append(d.strftime("%a %d")) 
                except: new_cols.append(date_str)
            display_df.columns = new_cols
            
            styled_df = display_df.style.map(highlight_shifts)
            st.dataframe(styled_df, use_container_width=True)
            
            csv = st.session_state['roster_data'].to_csv().encode('utf-8')
            st.download_button("📥 Download CSV", csv, "sats_roster.csv", "text/csv")

        st.divider()

        col_focus, col_validate = st.columns([2, 1])
        
        # 1. FOCUS EDITOR
        with col_focus:
            st.subheader("📝 Individual Schedule Editor")
            try:
                sorted_opts = sorted(st.session_state['roster_data'].index, key=lambda x: int(x[1:]) if x.startswith("S") and x[1:].isdigit() else x)
            except: sorted_opts = st.session_state['roster_data'].index
            
            selected_staff = st.selectbox("Select Staff ID", sorted_opts)
            
            with st.form("schedule_edit_form"):
                st.caption(f"Batch edit schedule for **{selected_staff}**.")
                staff_row = st.session_state['roster_data'].loc[selected_staff]
                staff_df = pd.DataFrame({"Date": staff_row.index, "Shift": staff_row.values})
                
                edited_staff_df = st.data_editor(
                    staff_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Date": st.column_config.TextColumn("Date", disabled=True),
                        "Shift": st.column_config.SelectboxColumn("Assigned Shift", options=shift_options, required=True, width="large")
                    },
                    key="focus_editor"
                )
                
                if st.form_submit_button("💾 Save Changes", type="primary"):
                    for idx, row in edited_staff_df.iterrows():
                        st.session_state['roster_data'].at[selected_staff, row['Date']] = row['Shift']
                    refresh_metrics()
                    st.toast("Schedule Updated Successfully!", icon="✅")
                    st.rerun()

        # 2. COMPLIANCE
        with col_validate:
            st.subheader("✅ Compliance Audit")
            if st.button("Run Compliance Check", type="primary"):
                user_assignments = []
                for staff_id, row in st.session_state['roster_data'].iterrows():
                    for date_str, shift_val in row.items():
                        user_assignments.append({'staff_id': staff_id, 'date': date_str, 'shift': shift_val})
                payload = {"assignments": user_assignments, "shift_definitions": st.session_state['shift_config_df'].to_dict('records'), "country": country_enum}
                try:
                    resp = requests.post(f"{API_URL}/validate", json=payload)
                    if resp.status_code == 200:
                        errors = resp.json()['errors']
                        st.session_state['validation_errors'] = errors
                        st.session_state['current_assignments'] = user_assignments
                        if not errors:
                            st.balloons()
                            st.success("100% Compliant.")
                        else: st.toast(f"Found {len(errors)} Violations", icon="⚠️")
                except: st.error("Validation Failed")

            if st.session_state['validation_errors']:
                for i, err in enumerate(st.session_state['validation_errors']):
                    with st.container(border=True):
                        st.markdown(f"**{err['type']}**")
                        st.caption(err['msg'])
                        
                        if st.button("🤖 Suggest Fix", key=f"s_{i}"):
                            try:
                                if err['type'] == "Understaffing":
                                    parts = err['msg'].split(" ")
                                    date_str = parts[2]
                                    shift_n = err['msg'].split("'")[1]
                                    violator = None
                                else:
                                    date_str = err['meta']['date']
                                    shift_n = err['meta']['shift']
                                    violator = err['meta']['violator']

                                rec_payload = {
                                    "date_target": date_str, "shift_name": shift_n,
                                    "assignments": st.session_state['current_assignments'],
                                    "shift_definitions": st.session_state['shift_config_df'].to_dict('records'),
                                    "staff_list": st.session_state['last_staff_list'], "country": country_enum
                                }
                                rec_resp = requests.post(f"{API_URL}/recommend", json=rec_payload)
                                if rec_resp.status_code == 200:
                                    res = rec_resp.json()['recommendation']
                                    st.session_state[f'rec_res_{i}'] = res
                                    st.session_state[f'rec_ctx_{i}'] = {'date': date_str, 'shift': shift_n, 'violator': violator}
                            except: pass

                        if f'rec_res_{i}' in st.session_state:
                            res = st.session_state[f'rec_res_{i}']
                            if res['candidate']:
                                st.success(res['message'])
                                if st.button("✅ Apply Fix", key=f"apply_{i}"):
                                    ctx = st.session_state[f'rec_ctx_{i}']
                                    st.session_state['roster_data'].at[res['candidate'], ctx['date']] = ctx['shift']
                                    if ctx['violator']: st.session_state['roster_data'].at[ctx['violator'], ctx['date']] = "Off"
                                    del st.session_state[f'rec_res_{i}']
                                    refresh_metrics()
                                    st.rerun()
                            else: st.warning("No staff available.")

                        if err['type'] != "Understaffing":
                             with st.expander("⚖️ View Regulation"):
                                 if err.get('search_query'):
                                     try:
                                         l_resp = requests.get(
                                             f"{API_URL}/compliance/search", 
                                             params={"query": err['search_query'], "country": country_enum}
                                         )
                                         if l_resp.status_code == 200 and l_resp.json(): 
                                             res = l_resp.json()[0]
                                             st.info(res['law_text'])
                                             st.caption(f"Source: {res['source']}")
                                     except: pass

# =========================================================
# TAB 4: LEGAL KNOWLEDGE
# =========================================================
with tab_legal:
    st.header("Legal Knowledge Base")
    q = st.text_input("Search Labor Regulations", "")
    if q and server_status:
        try:
            resp = requests.get(f"{API_URL}/compliance/search", params={"query": q})
            if resp.status_code == 200:
                for r in resp.json():
                    with st.container(border=True):
                        st.markdown(f"**Source:** `{r['source']}`")
                        st.markdown(f"> {r['law_text']}")
        except: st.error("Search Failed")