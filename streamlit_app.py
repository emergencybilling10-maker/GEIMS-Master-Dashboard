import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- NEW: FUTURISTIC UI STYLING ---
st.markdown("""
    <style>
    /* Main Background and Font */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    /* Neumorphic/Glassmorphism Cards */
    div[data-testid="stExpander"], .stForm, div[data-testid="stMetricValue"] {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
        backdrop-filter: blur(10px);
        padding: 20px;
    }
    
    /* Futuristic Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        letter-spacing: -1px;
        color: #38bdf8;
        text-transform: uppercase;
    }
    
    /* Buttons Customization */
    .stButton>button {
        background: linear-gradient(90deg, #0ea5e9 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        transition: all 0.3s ease;
        font-weight: bold;
        text-transform: uppercase;
    }
    .stButton>button:hover {
        box-shadow: 0 0 15px rgba(14, 165, 233, 0.6);
        transform: translateY(-2px);
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95);
        border-right: 1px solid rgba(56, 189, 248, 0.2);
    }
    
    /* Bed Status Cards Styling */
    .bed-card {
        border-radius: 12px;
        transition: transform 0.2s;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .bed-card:hover {
        transform: scale(1.02);
    }
    
    /* Input Fields */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: rgba(0,0,0,0.2) !important;
        color: white !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. SECURE DATABASE CONNECTION ---
@st.cache_resource
def get_db():
    if "textkey" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds)
        except Exception as e:
            st.error(f"Database Connection Error: {e}")
    return None

db = get_db()

# --- 2. BED STRUCTURE ---
bed_structure = {
    "Eighth Floor - B Wing": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "Ninth Floor - A Wing": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "Ninth Floor - B Wing": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "Ninth Floor - C Wing": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "Ninth Floor - F Wing": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
}
all_bed_ids = [b for w in bed_structure.values() for b in w]

# --- 3. FAILSAFE DATA FETCH ---
if db:
    if 'cached_live_data' not in st.session_state or 'cached_req_list' not in st.session_state:
        status_doc = db.collection("settings").document("dashboard_status").get()
        st.session_state.is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"
        docs = db.collection("beds").stream()
        st.session_state.cached_live_data = {doc.id: doc.to_dict() for doc in docs}
        
        reqs_stream = db.collection("bed_requests").limit(100).stream()
        raw_reqs = [r.to_dict() | {'ID': r.id} for r in reqs_stream]
        st.session_state.cached_req_list = sorted(raw_reqs, key=lambda x: (x.get('position', 999), x.get('timestamp', datetime.min)))
        
        book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).stream()
        st.session_state.cached_book_list = [b.to_dict() | {'ID': b.id} for b in book_stream]

    live_data = st.session_state.cached_live_data
    req_list = st.session_state.cached_req_list
    book_list = st.session_state.cached_book_list
else:
    st.error("Database Connection Failed."); st.stop()

# --- 4. HEADER ---
tz = pytz.timezone('Asia/Kolkata')
today_date_str = datetime.now(tz).strftime('%d/%m/%Y')
today_iso = datetime.now(tz).strftime('%Y-%m-%d')

st.markdown("<h1 style='text-align: center; color: #38bdf8;'>GEIMS COMMAND CENTER</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #94a3b8;'>SYSTEM STATUS: <span style='color:#4ade80;'>ACTIVE</span> | {today_date_str}</p>", unsafe_allow_html=True)

if st.button("🔄 Refresh System Neural Link"):
    for key in ['cached_live_data', 'is_live', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='background-color: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; padding: 15px; border-radius: 10px; margin-bottom: 10px;'><b>⚠️ INCOMING PATIENT: {a.get('name', 'N/A')}</b></div>", unsafe_allow_html=True)
        if st.button(f"Confirm Admission: {a.get('name')}", key=f"ack_{a['ID']}"):
            db.collection("bed_requests").add({
                "timestamp": datetime.now(tz), "name": a.get('name'), "category": a.get('category', 'OTHER'),
                "dr_name": a.get('dr'), "shift_from": "BOOKING", "shift_to": a.get('preference', 'PVT'), 
                "remark": f"Reserved: {a.get('pref_bed','-')}", "bed_no": "", "status": "WAITING", 
                "date": today_date_str, "position": 999
            })
            db.collection("future_bookings").document(a['ID']).delete()
            for k in ['cached_req_list', 'cached_book_list']: 
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# --- 6. MANAGE PATIENT REQUESTS ---
with st.expander("📊 DATA LOGS: PATIENT REQUESTS", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('status') == "DONE")
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("PENDING QUEUE", pending)
    c_m2.metric("TOTAL COMPLETED", allotted)
    st.divider()

    with st.form("new_req", clear_on_submit=True):
        st.subheader("Add Admission Protocol")
        c1, c2 = st.columns(2)
        p_name = c1.text_input("PATIENT NAME")
        p_cat = c1.selectbox("CATEGORY", ["SELF PAY", "ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "ICAR", "AYUSHMAN", "OTHER"])
        dr_name = c1.text_input("ADMITTED UNDER DOCTOR")
        p_fr = c2.selectbox("SHIFT FROM", ["CCU", "EMERGENCY", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
        p_to = c2.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        rem = c2.text_input("REMARK")
        if st.form_submit_button("Initialize Entry"):
            if p_name:
                db.collection("bed_requests").add({
                    "timestamp": datetime.now(tz), "name": p_name, "category": p_cat,
                    "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                    "remark": rem, "bed_no": "", "status": "WAITING", "date": today_date_str, "position": 999
                })
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

    if req_list:
        st.divider()
        sq = st.text_input("🔍 Neural Search Patient Database", "").lower()
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["SN", "NAME", "CAT", "DR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.markdown(f"<b style='color:#38bdf8;'>{h}</b>", unsafe_allow_html=True)
        for idx, r in enumerate(req_list):
            if sq and sq not in r.get('name', '').lower(): continue
            
            current_status = r.get('status', 'WAITING')
            b_no = r.get('bed_no', '')
            if b_no and current_status == "WAITING": current_status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-')); r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-')); r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
            color_map = {"DONE": "#4ade80", "CANCELLED": "#f87171", "GEN-WARD ALLOTTED": "#60a5fa", "HOLD": "#c084fc"}
            color = color_map.get(current_status, "#fbbf24")
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{current_status}</span>", unsafe_allow_html=True)
            if current_status == "DONE":
                slip = f"""====================================\n      G.E.I.M.S (Bed Management)\n      BED ALLOTMENT SLIP\n====================================\nDATE: {today_date_str}\nPATIENT: {r['name']}\n------------------------------------\nBED:  {b_no}\n===================================="""
                r_cols[9].download_button("🖨️ SLIP", data=slip, file_name=f"Slip_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- PDF CONSENT PANEL ---
st.subheader("📑 DIGITAL CONSENT ARCHIVE")
def get_pdf_data(file_name):
    try:
        with open(file_name, "rb") as f: return f.read()
    except FileNotFoundError: return None

c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns(5)
# (Your PDF logic remains exactly same, just wrapped in cleaner columns)
pdfs = [("💳 SELF PAY", "consent_self_pay.pdf"), ("💰 CGHS CASH", "consent_cghs_cash.pdf"), 
        ("🎖️ ECHS", "consent_echs.pdf"), ("🏥 CREDIT/PSU", "consent_cghs_credit.pdf"), ("🏢 TPA", "consent_tpa.pdf")]
cols = [c_col1, c_col2, c_col3, c_col4, c_col5]

for col, (label, file) in zip(cols, pdfs):
    data = get_pdf_data(file)
    with col:
        if data: st.download_button(label, data, file_name=file, mime="application/pdf")
        else: st.error(f"{label} NA")

# --- 7. SIDEBAR ---
show_dashboard = False 
with st.sidebar:
    st.header("⚡ COMMAND PANEL")
    with st.expander("📅 FUTURE SCHEDULER"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Patient Name"); f_uhid = st.text_input("UHID No."); f_dr = st.text_input("Doctor Name")
            f_date = st.date_input("Booking Date"); f_room = st.text_input("Pre-decided Bed ID")
            f_cat = st.selectbox("Category", ["SELF PAY", "OTHER"]); f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            if st.form_submit_button("Sync Future Booking"):
                db.collection("future_bookings").add({"name": f_name, "uhid": f_uhid, "dr": f_dr, "book_date": f_date.strftime('%Y-%m-%d'), "category": f_cat, "preference": f_pref, "pref_bed": f_room})
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    st.divider()
    pw = st.text_input("System Access Key", type="password")
    if pw == "GeimsAdmin99":
        show_dashboard = True 
        st.success("Access Granted")
        
        # Reports
        if st.button("Generate Handover Data"):
            done = [r for r in req_list if r.get('bed_no')]
            rep = f"GEIMS SHIFT REPORT - {today_date_str}\n\n"
            for r in done: rep += f"- {r['name']} -> Bed: {r['bed_no']}\n"
            st.download_button("📥 Download Byte-Stream", data=rep, file_name=f"Report_{today_date_str}.txt")

        # Patient Modification Hub (logic unchanged)
        st.divider(); st.subheader("🛠️ ARCHIVE TOOLS")
        if req_list:
            p_map = {f"{r['name']} ({r.get('bed_no', 'No Bed')})": r['ID'] for r in req_list}
            selected_label = st.selectbox("Select Record", list(p_map.keys()))
            target_id = p_map[selected_label]
            target_data = next(r for r in req_list if r['ID'] == target_id)
            new_status = st.selectbox("Update Status", ["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"], index=["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"].index(target_data.get('status', 'WAITING')))
            new_bed = st.text_input("Update Bed ID", value=target_data.get('bed_no', ''))
            if st.button("🔥 PUSH UPDATE"):
                old_bed = target_data.get('bed_no')
                if old_bed and old_bed in all_bed_ids: db.collection("beds").document(old_bed).set({"status": "VACANT", "patient": ""})
                if new_bed and new_bed in all_bed_ids and new_status == "DONE": db.collection("beds").document(new_bed).set({"status": "ALLOTTED", "patient": target_data['name']})
                db.collection("bed_requests").document(target_id).update({"status": new_status, "bed_no": new_bed})
                for k in ['cached_req_list', 'cached_live_data']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

        # Admin reset tools (Keeping your exact logic)
        st.error("DANGER ZONE")
        if st.button("WIPE ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.rerun()

# --- 8. VISUAL DASHBOARD ---
if show_dashboard:
    status_colors = {"VACANT": "rgba(255,255,255,0.1)", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#60a5fa", "MAINTENANCE": "#475569", "RESTRICTED": "#ef4444"}
    st.markdown("### 🛰️ LIVE BED TOPOLOGY")
    for wing, beds in bed_structure.items():
        st.markdown(f"#### {wing}")
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "rgba(255,255,255,0.1)")
            txt = "white" if data.get('status') in ["ALLOTTED", "RESTRICTED", "MAINTENANCE"] else "white"
            border = "2px solid #38bdf8" if data.get('status') == "ALLOTTED" else "1px solid rgba(255,255,255,0.1)"
            
            with cols[i % 5]:
                st.markdown(f'''
                    <div class="bed-card" style="background-color:{bg}; color:{txt}; padding:10px; border:{border}; text-align:center; height:100px;">
                        <div style="font-size:12px; font-weight:bold;">{bed}</div>
                        <div style="font-size:10px; opacity:0.8; margin-top:5px;">{data.get("status", "VACANT")}</div>
                        <div style="font-size:11px; margin-top:5px; color:#38bdf8;">{data.get("patient", "")}</div>
                    </div>
                ''', unsafe_allow_html=True)
else:
    st.info("🔒 SYSTEM ENCRYPTED. Enter Admin Access Key in sidebar to view visual topology.")
