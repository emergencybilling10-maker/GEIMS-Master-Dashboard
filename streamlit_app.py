import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS NEURAL LINK", layout="wide")

# --- CYBERPUNK THEME ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    /* Global Cyberpunk Reset */
    .stApp {
        background-color: #050505;
        background-image: 
            linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), 
            linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
        background-size: 100% 2px, 3px 100%;
        color: #00ff41; /* Matrix Green */
        font-family: 'Rajdhani', sans-serif;
    }

    /* Cyber Containers */
    div[data-testid="stExpander"], .stForm, div[data-testid="stMetricValue"] {
        background: rgba(20, 20, 20, 0.85) !important;
        border: 2px solid #00f3ff !important; /* Cyber Blue */
        box-shadow: 0px 0px 15px #00f3ff;
        border-radius: 0px !important; /* Sharp edges for cyberpunk */
        clip-path: polygon(0% 0%, 100% 0%, 100% 90%, 95% 100%, 0% 100%);
    }

    /* Titles */
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif;
        color: #ff003c !important; /* Cyber Pink */
        text-shadow: 2px 2px #00f3ff;
        text-transform: uppercase;
        letter-spacing: 5px;
    }

    /* Neon Buttons */
    .stButton>button {
        width: 100%;
        background: transparent;
        color: #ff003c;
        border: 2px solid #ff003c !important;
        font-family: 'Orbitron', sans-serif;
        font-weight: bold;
        transition: 0.3s;
        text-shadow: 0 0 5px #ff003c;
    }
    .stButton>button:hover {
        background: #ff003c !important;
        color: white !important;
        box-shadow: 0 0 20px #ff003c;
    }

    /* Sidebar - Deep Tech Look */
    section[data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 2px solid #ff003c;
    }

    /* Status Text */
    .stMetric label { color: #00f3ff !important; font-size: 1.2rem !important; }
    
    /* Input Fields */
    input, select, textarea {
        background-color: #1a1a1a !important;
        color: #00f3ff !important;
        border: 1px solid #00f3ff !important;
    }

    /* Custom Bed Cards */
    .bed-node {
        border-left: 5px solid #00f3ff;
        padding: 10px;
        margin: 5px;
        background: #111;
        font-family: 'Rajdhani', sans-serif;
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
            st.error(f"DATABASE_LINK_CRITICAL_FAILURE: {e}")
    return None

db = get_db()

# --- 2. BED STRUCTURE ---
bed_structure = {
    "SECTOR_8_B": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "SECTOR_9_A": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "SECTOR_9_B": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "SECTOR_9_C": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "SECTOR_9_F": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
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
    st.error("SYSTEM_OFFLINE: CHECK DB_LINK"); st.stop()

# --- 4. HEADER ---
tz = pytz.timezone('Asia/Kolkata')
today_date_str = datetime.now(tz).strftime('%d/%m/%Y')
today_iso = datetime.now(tz).strftime('%Y-%m-%d')

st.markdown("<h1 style='text-align: center;'>GEIMS // NEURAL-LINK</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #00f3ff;'>STARDATE: {today_date_str} // ENCRYPTION: ACTIVE</p>", unsafe_allow_html=True)

if st.button("RE-INITIALIZE NEURAL LINK"):
    for key in ['cached_live_data', 'is_live', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='border-left: 10px solid #ff003c; padding: 10px; background: rgba(255, 0, 60, 0.1); margin-bottom: 10px;'>[SYSTEM_WARNING]: INBOUND_UNIT_DETECTION: {a.get('name', 'N/A')}</div>", unsafe_allow_html=True)
        if st.button(f"ENGAGE ADMISSION: {a.get('name')}", key=f"ack_{a['ID']}"):
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
with st.expander(">> ACCESS DATA_CORE: PATIENT_QUEUE", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('status') == "DONE")
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("UNASSIGNED_UNITS", pending)
    c_m2.metric("SYNCHRONIZED_UNITS", allotted)
    st.divider()

    with st.form("new_req", clear_on_submit=True):
        st.subheader(">> INPUT NEW SEQUENCE")
        c1, c2 = st.columns(2)
        p_name = c1.text_input("UNIT_NAME")
        p_cat = c1.selectbox("TAG_CATEGORY", ["SELF PAY", "ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "ICAR", "AYUSHMAN", "OTHER"])
        dr_name = c1.text_input("SUPERVISING_OFFICER (DR)")
        p_fr = c2.selectbox("ORIGIN_POINT", ["CCU", "EMERGENCY", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
        p_to = c2.selectbox("TARGET_DESTINATION", ["DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        rem = c2.text_input("LOG_REMARK")
        if st.form_submit_button("COMMIT TO CHAIN"):
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
        sq = st.text_input(">> SCAN_FOR_NAME...", "").lower()
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["#", "UNIT", "TAG", "SUPV", "SRC", "DST", "LOG", "NODE", "STATE", "LINK"]
        for col, h in zip(h_cols, headers): col.markdown(f"<b style='color:#ff003c;'>{h}</b>", unsafe_allow_html=True)
        for idx, r in enumerate(req_list):
            if sq and sq not in r.get('name', '').lower(): continue
            current_status = r.get('status', 'WAITING')
            b_no = r.get('bed_no', '')
            if b_no and current_status == "WAITING": current_status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-')); r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-')); r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
            color_map = {"DONE": "#00ff41", "CANCELLED": "#ff003c", "GEN-WARD ALLOTTED": "#00f3ff", "HOLD": "#fbbf24"}
            color = color_map.get(current_status, "#00f3ff")
            r_cols[8].markdown(f"<span style='color:{color};'>{current_status}</span>", unsafe_allow_html=True)
            if current_status == "DONE":
                slip = f"""CYBER_PUNK_GEIMS_ALLOTMENT\n=========================\nPATIENT: {r['name']}\nNODE: {b_no}\nSTARDATE: {today_date_str}"""
                r_cols[9].download_button("DATA_SLIP", data=slip, file_name=f"Unit_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- 7. SIDEBAR ---
show_dashboard = False 
with st.sidebar:
    st.header(">> CORE_TERMINAL")
    pw = st.text_input("ENCRYPTION_KEY", type="password")
    if pw == "GeimsAdmin99":
        show_dashboard = True 
        st.success("ACCESS_GRANTED")
        # (Rest of your original sidebar logic for admin stays here, just update labels to be "Cyber")
        if st.button("EXTRACT HANDOVER_BYTE"):
            done = [r for r in req_list if r.get('bed_no')]
            rep = f"GEIMS_DUMP_{today_date_str}\n" + "".join([f"- {r['name']} > {r['bed_no']}\n" for r in done])
            st.download_button("DOWNLOAD_LOG", data=rep, file_name=f"GEIMS_{today_date_str}.txt")

# --- 8. VISUAL DASHBOARD ---
if show_dashboard:
    status_colors = {"VACANT": "#111", "BOOKED": "rgba(0, 243, 255, 0.2)", "ALLOTTED": "#ff003c", "DISCHARGE": "#00ff41", "MAINTENANCE": "#444", "RESTRICTED": "#550000"}
    st.markdown("### >> LIVE_NEURAL_TOPOLOGY")
    for wing, beds in bed_structure.items():
        st.markdown(f"#### // {wing}")
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "#111")
            border = "#ff003c" if data.get('status') == "ALLOTTED" else "#00f3ff"
            with cols[i % 5]:
                st.markdown(f'''
                    <div style="border: 1px solid {border}; background: {bg}; padding: 10px; text-align: center; margin-bottom: 5px;">
                        <div style="color:{border}; font-weight:bold; font-size:12px;">{bed}</div>
                        <div style="font-size:10px; color:#fff;">{data.get("status", "VACANT")}</div>
                        <div style="font-size:11px; color:#00ff41;">{data.get("patient", "")}</div>
                    </div>
                ''', unsafe_allow_html=True)
else:
    st.info(">> TERMINAL_LOCKED. PLEASE_INPUT_ENCRYPTION_KEY.")
