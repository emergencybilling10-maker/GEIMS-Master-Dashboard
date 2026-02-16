import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config - Optimized for maximum speed
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 1. FAST DATABASE CONNECTION ---
@st.cache_resource
def get_db():
    if "textkey" in st.secrets:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds)
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

# --- 3. LIVE DATA FETCH (Optimized for Large Data) ---
status_ref = db.collection("settings").document("dashboard_status")
is_live = status_ref.get().to_dict().get("status", "LIVE") if status_ref.get().exists else "LIVE"

# Only load Bed Grid Data initially
docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}

# --- 4. HEADER & LIVE DATE ---
st.markdown("<h1 style='text-align: center;'>Graphic Era Institute of Medical Sciences - GEIMS</h1>", unsafe_allow_html=True)
tz = pytz.timezone('Asia/Kolkata')
live_date_str = datetime.now(tz).strftime('%d/%m/%Y') # Live Date Fixed

if is_live == "LIVE":
    total = len(all_bed_ids)
    occupied = sum(1 for b in live_data.values() if b.get('status') in ["ALLOTTED", "BOOKED", "RESTRICTED"])
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Occupancy %", f"{round((occupied/total)*100) if total > 0 else 0}%")
    m2.metric("Available Beds", total - occupied)
    m3.metric("Live Date", live_date_str)
st.divider()

# --- 5. PATIENT BED REQUEST PLATFORM (Manual Load to prevent freezing) ---
with st.expander("📋 MANAGE BED REQUESTS (Click to load data)"):
    # NEW: Form for submission
    with st.form("shifting_form", clear_on_submit=True):
        st.subheader("New Shifting Request")
        c1, c2 = st.columns(2)
        name = c1.text_input("PATIENT NAME")
        cat = c1.selectbox("CATEGORY", ["ECHS", "TPA", "CGHS CREDIT", "SELF PAY", "CGHS CASH", "ESI", "AYUSHMAN", "OTHER"])
        fr = c2.selectbox("SHIFT FROM", ["CCU", "ICU", "WARD", "LR", "OTHER"])
        to = c2.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
        if st.form_submit_button("Submit Request"):
            if name:
                db.collection("bed_requests").add({
                    "timestamp": datetime.now(), "name": name, "category": cat,
                    "shift_from": fr, "shift_to": to, "bed_no": ""
                })
                st.rerun()

    # Load only the 50 most recent requests to ensure speed
    requests_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
    req_list = []
    for r in requests_stream:
        d = r.to_dict()
        d['ID'] = r.id
        req_list.append(d)

    if req_list:
        st.subheader("📝 Edit or Remove Entry")
        target = st.selectbox("Select Patient", [r['name'] for r in req_list])
        if st.button("🗑️ DELETE SELECTED ENTRY"):
            r_id = next(r['ID'] for r in req_list if r['name'] == target)
            db.collection("bed_requests").document(r_id).delete()
            st.rerun()

        st.subheader("Current Request List")
        st.dataframe(pd.DataFrame(req_list).drop(columns=['ID', 'timestamp'], errors='ignore'), use_container_width=True)

# --- 6. ADMIN PANEL & SYNC ---
with st.sidebar:
    st.header("🔐 Admin Controls")
    pwd = st.text_input("Password", type="password")
    if pwd == "Geims248001":
        st.subheader("Allotment & Sync")
        if 'req_list' in locals():
            waiting = [r for r in req_list if not r.get('bed_no')]
            if waiting:
                p_sel = st.selectbox("Allot Bed to", [r['name'] for r in waiting])
                b_val = st.text_input("Bed No.")
                if st.button("Sync & Finalize"):
                    # Sync Request and Dashboard
                    r_id = next(r['ID'] for r in waiting if r['name'] == p_sel)
                    db.collection("bed_requests").document(r_id).update({"bed_no": b_val})
                    if b_val in all_bed_ids:
                        db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                    st.rerun()

    if pwd == "GeimsAdmin99":
        st.subheader("⚙️ System Admin")
        if st.button("RESET LIST"):
            for r in db.collection("bed_requests").stream(): r.reference.delete()
            st.rerun()
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.rerun()

# --- 7. DASHBOARD DISPLAY ---
if is_live != "LIVE":
    st.error("⚠️ DASHBOARD IS OFFLINE")
    st.stop()

st.title("🏥 Live Bed Status")
status_colors = {"VACANT": "#FFFFFF", "RESTRICTED": "#FF0000", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0"}



for wing, beds in bed_structure.items():
    st.subheader(wing)
    cols = st.columns(5)
    for i, bed in enumerate(beds):
        data = live_data.get(bed, {"status": "VACANT", "patient": ""})
        bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
        txt = "white" if data.get('status') in ["ALLOTTED", "RESTRICTED"] else "black"
        with cols[i % 5]:
            st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:70px; margin-bottom:5px;"><div style="font-size:11px; font-weight:bold;">{bed}</div><div style="font-size:10px;">{data.get("patient", "")}</div></div>', unsafe_allow_html=True)
    st.divider()
