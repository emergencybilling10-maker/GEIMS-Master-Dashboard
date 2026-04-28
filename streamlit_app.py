import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- ADVANCED AI UI STYLING (LIGHT THEME) ---
st.markdown("""
    <style>
    /* Global Background */
    .main {
        background-color: #f0f4f8;
        background-image: radial-gradient(#d1d9e6 0.5px, transparent 0.5px);
        background-size: 20px 20px;
    }

    /* AI Glow Headers */
    h1 {
        color: #1e3a8a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 800 !important;
        text-shadow: 0px 0px 12px rgba(37, 99, 235, 0.2);
        letter-spacing: -0.5px;
    }

    /* Glassmorphism Containers */
    div[data-testid="stExpander"], .stForm, .stMetric {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07) !important;
    }

    /* Advanced Click Feel Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 10px !important;
        border: none !important;
        background: linear-gradient(145deg, #ffffff, #e6e9f0) !important;
        box-shadow: 4px 4px 8px #d1d9e6, -4px -4px 8px #ffffff !important;
        color: #2563eb !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        height: 45px;
    }

    .stButton>button:hover {
        background: #2563eb !important;
        color: white !important;
        transform: translateY(-2px);
        box-shadow: 0px 10px 20px rgba(37, 99, 235, 0.2) !important;
    }

    .stButton>button:active {
        transform: translateY(2px) !important;
        box-shadow: inset 4px 4px 8px #d1d9e6, inset -4px -4px 8px #ffffff !important;
    }
    
    /* Download Button Specific (Tactile Feel) */
    .stDownloadButton>button {
        background: linear-gradient(145deg, #e0f2fe, #f0f9ff) !important;
        border: 1px solid #bae6fd !important;
    }

    /* Metrics Styling */
    div[data-testid="stMetricValue"] {
        color: #2563eb !important;
        font-family: 'Courier New', monospace;
    }

    /* Bed Status Cards (Visual Dashboard) */
    .bed-card {
        transition: all 0.3s ease;
        border: none !important;
        box-shadow: 5px 5px 10px #d1d9e6, -5px -5px 10px #ffffff;
    }
    .bed-card:hover {
        transform: scale(1.05);
        z-index: 10;
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

st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>GEIMS AI BED COMMAND</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #64748b;'><b>CORE SYSTEM ARCHIVE: {today_date_str}</b></p>", unsafe_allow_html=True)

if st.button("🔄 Sync Neural Database"):
    for key in ['cached_live_data', 'is_live', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='background-color: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 10px; margin-bottom: 10px;'><b style='color:#dc2626'>⚡ PRIORITY ADMISSION: {a.get('name', 'N/A')}</b></div>", unsafe_allow_html=True)
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
with st.expander("📡 REAL-TIME SHIFTING MONITOR", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('status') == "DONE")
    m1, m2 = st.columns(2)
    m1.metric("Pending Queue", pending)
    m2.metric("Successful Shifts", allotted)
    st.divider()

    with st.form("new_req", clear_on_submit=True):
        st.subheader("Initialize New Shift Protocol")
        c1, c2 = st.columns(2)
        p_name = c1.text_input("PATIENT NAME")
        p_cat = c1.selectbox("CATEGORY", ["SELF PAY", "ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "ICAR", "AYUSHMAN", "OTHER"])
        dr_name = c1.text_input("ADMITTED UNDER DOCTOR")
        p_fr = c2.selectbox("SHIFT FROM", ["CCU", "EMERGENCY", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
        p_to = c2.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        rem = c2.text_input("REMARK")
        if st.form_submit_button("Transmit Request"):
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
        headers = ["S.N", "NAME", "CAT", "DR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        for idx, r in enumerate(req_list):
            if sq and sq not in r.get('name', '').lower(): continue
            
            current_status = r.get('status', 'WAITING')
            b_no = r.get('bed_no', '')
            if b_no and current_status == "WAITING": current_status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-')); r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-')); r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
            color_map = {"DONE": "#16a34a", "CANCELLED": "#dc2626", "GEN-WARD ALLOTTED": "#2563eb", "HOLD": "#9333ea"}
            color = color_map.get(current_status, "#ea580c")
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{current_status}</span>", unsafe_allow_html=True)
            if current_status == "DONE":
                slip = f"""====================================\n      G.E.I.M.S (AI Bed System)\n      ALLOTMENT PROTOCOL\n====================================\nDATE: {today_date_str}\nPATIENT: {r['name']}\n------------------------------------\nBED:  {b_no}\n===================================="""
                r_cols[9].download_button("💾 Export Slip", data=slip, file_name=f"Slip_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- NEW: PDF CONSENT FORM PANEL ---
st.subheader("📑 DIGITAL CONSENT ARCHIVE")

def get_pdf_data(file_name):
    try:
        with open(file_name, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns(5)

# (Individual buttons kept exactly same, UI styles them automatically)
pdf_self = get_pdf_data("consent_self_pay.pdf")
with c_col1:
    if pdf_self: st.download_button("💳 SELF PAY", pdf_self, file_name="Consent_SelfPay.pdf", mime="application/pdf")
    else: st.error("NA")

pdf_cghs_cash = get_pdf_data("consent_cghs_cash.pdf")
with c_col2:
    if pdf_cghs_cash: st.download_button("💰 CGHS CASH", pdf_cghs_cash, file_name="Consent_CGHS_Cash.pdf", mime="application/pdf")
    else: st.error("NA")

pdf_echs = get_pdf_data("consent_echs.pdf")
with c_col3:
    if pdf_echs: st.download_button("🎖️ ECHS", pdf_echs, file_name="Consent_ECHS.pdf", mime="application/pdf")
    else: st.error("NA")

pdf_cghs_credit = get_pdf_data("consent_cghs_credit.pdf")
with c_col4:
    if pdf_cghs_credit: st.download_button("🏥 CGHS CREDIT", pdf_cghs_credit, file_name="Consent_CGHS_Credit.pdf", mime="application/pdf")
    else: st.error("NA")

pdf_tpa = get_pdf_data("consent_tpa.pdf")
with c_col5:
    if pdf_tpa: st.download_button("🏢 TPA", pdf_tpa, file_name="Consent_TPA.pdf", mime="application/pdf")
    else: st.error("NA")

# --- 7. SIDEBAR ---
show_dashboard = False 
with st.sidebar:
    st.header("⚡ SYSTEM PROTOCOL")
    with st.expander("📝 NEW RESERVATION"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Patient Name"); f_uhid = st.text_input("UHID No."); f_dr = st.text_input("Doctor Name")
            f_date = st.date_input("Booking Date"); f_room = st.text_input("Pre-decided Bed ID"); f_cat = st.selectbox("Category", ["SELF PAY", "OTHER"]); f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            if st.form_submit_button("Secure Booking"):
                db.collection("future_bookings").add({"name": f_name, "uhid": f_uhid, "dr": f_dr, "book_date": f_date.strftime('%Y-%m-%d'), "category": f_cat, "preference": f_pref, "pref_bed": f_room})
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    st.divider(); st.header("🔑 SECURE ACCESS")
    if st.text_input("Access Key", type="password") == "GeimsAdmin99":
        show_dashboard = True 
        
        # 📋 REPORTS
        st.subheader("📋 Data Export")
        if st.button("Generate Handover Data"):
            done = [r for r in req_list if r.get('bed_no')]
            rep = f"GEIMS AI LOG - {today_date_str}\n\n"
            for r in done: rep += f"- {r['name']} -> Bed: {r['bed_no']}\n"
            st.download_button("📥 Download Byte-Stream", data=rep, file_name=f"Handover_{today_date_str}.txt")

        # --- ADMIN TOOLS (Kept exactly same as your logic) ---
        st.divider(); st.subheader("🛠️ Neural Override Hub")
        if req_list:
            p_map = {f"{r['name']} ({r.get('bed_no', 'No Bed')})": r['ID'] for r in req_list}
            selected_label = st.selectbox("Select Record", list(p_map.keys()))
            target_id = p_map[selected_label]
            target_data = next(r for r in req_list if r['ID'] == target_id)
            new_status = st.selectbox("Status Update", ["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"], index=["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"].index(target_data.get('status', 'WAITING')))
            new_bed = st.text_input("Manual Bed Assignment", value=target_data.get('bed_no', ''))
            if st.button("🔥 PUSH GLOBAL SYNC"):
                old_bed = target_data.get('bed_no')
                if old_bed and old_bed in all_bed_ids: db.collection("beds").document(old_bed).set({"status": "VACANT", "patient": ""})
                if new_bed and new_bed in all_bed_ids and new_status == "DONE": db.collection("beds").document(new_bed).set({"status": "ALLOTTED", "patient": target_data['name']})
                db.collection("bed_requests").document(target_id).update({"status": new_status, "bed_no": new_bed})
                for k in ['cached_req_list', 'cached_live_data']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

# --- 8. VISUAL DASHBOARD ---
if show_dashboard:
    status_colors = {"VACANT": "#f8fafc", "BOOKED": "#dcfce7", "ALLOTTED": "#1e293b", "DISCHARGE": "#e0f2fe", "MAINTENANCE": "#f1f5f9", "RESTRICTED": "#fee2e2"}
    st.title("🛰️ LIVE BED TOPOLOGY")
    for wing, beds in bed_structure.items():
        st.subheader(wing); cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
            txt = "#f8fafc" if data.get('status') in ["ALLOTTED", "RESTRICTED"] else "#334155"
            with cols[i % 5]:
                st.markdown(f'''
                    <div class="bed-card" style="background-color:{bg}; color:{txt}; padding:10px; border:1px solid #e2e8f0; border-radius:12px; text-align:center; height:95px; font-size:11px;">
                        <b style="font-size:13px;">{bed}</b><br>
                        <span style="font-size:10px; font-weight:bold; opacity:0.8;">{data.get("status", "VACANT")}</span><br>
                        <i style="font-size:10px; color:#2563eb;">{data.get("patient", "")}</i>
                    </div>
                ''', unsafe_allow_html=True)
else:
    st.info("🔒 SYSTEM ENCRYPTED: Enter Neural Access Key in Sidebar.")
