import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config - Forced Wide and Fast
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 1. DATABASE CONNECTION (HIGH-SPEED CACHE) ---
@st.cache_resource(ttl=3600)
def get_db():
    try:
        if "textkey" in st.secrets:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds)
    except Exception as e:
        st.error(f"Database Connection Failed: {e}")
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

# --- 3. FETCH ESSENTIALS ---
status_ref = db.collection("settings").document("dashboard_status")
is_live = status_ref.get().to_dict().get("status", "LIVE") if status_ref.get().exists else "LIVE"

# --- 4. TOP METRICS & LIVE DATE ---
st.markdown("<h1 style='text-align: center;'>Graphic Era Institute of Medical Sciences - GEIMS</h1>", unsafe_allow_html=True)
tz = pytz.timezone('Asia/Kolkata')
live_date = datetime.now(tz).strftime('%d/%m/%Y')

# Quick count without full object load
bed_docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in bed_docs}
occ_beds = sum(1 for b in live_data.values() if b.get('status') in ["ALLOTTED", "BOOKED", "RESTRICTED"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Occupancy %", f"{round((occ_beds/len(all_bed_ids))*100)}%")
m2.metric("Available Beds", len(all_bed_ids) - occ_beds)
m3.metric("Live Date", live_date)
m4.button("🔄 Refresh Data", on_click=st.cache_resource.clear) # Force Clear Cache
st.divider()

# --- 5. PATIENT BED REQUEST PLATFORM (LAZY LOADED) ---
with st.expander("📋 MANAGE BED REQUESTS (Click to Open)"):
    # Form
    with st.form("new_shift", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("PATIENT NAME")
        cat = c1.selectbox("CATEGORY", ["ECHS", "TPA", "CGHS CREDIT", "SELF PAY", "AYUSHMAN", "OTHER"])
        dr = c1.text_input("DOCTOR")
        fr = c2.selectbox("FROM", ["CCU", "ICU", "WARD", "LR", "OTHER"])
        to = c2.selectbox("TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
        rem = c2.text_input("REMARK")
        if st.form_submit_button("Submit Request"):
            db.collection("bed_requests").add({
                "timestamp": datetime.now(), "date": live_date, "name": name,
                "category": cat, "dr_name": dr, "shift_from": fr, "shift_to": to,
                "remark": rem, "bed_no": ""
            })
            st.rerun()

    st.divider()
    
    # Load Shifting Data ONLY when expanded
    shifting_data = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()
    req_list = []
    for r in shifting_data:
        d = r.to_dict()
        d['ID'] = r.id
        req_list.append(d)

    if req_list:
        # Edit/Remove logic restored
        e1, e2 = st.columns(2)
        target = e1.selectbox("Edit/Remove Patient", [r['name'] for r in req_list])
        action = e1.radio("Action", ["Edit Remark", "Delete Entry"], horizontal=True)
        new_rem = e2.text_input("New Remark")
        if st.button("Apply Action"):
            r_id = next(r['ID'] for r in req_list if r['name'] == target)
            if action == "Delete Entry":
                db.collection("bed_requests").document(r_id).delete()
            else:
                db.collection("bed_requests").document(r_id).update({"remark": new_rem})
            st.rerun()

        st.divider()
        st.dataframe(pd.DataFrame(req_list).drop(columns=['ID', 'timestamp'], errors='ignore'), use_container_width=True)

# --- 6. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🔐 Admin Panel")
    pwd = st.text_input("Password", type="password")
    if pwd == "Geims248001":
        st.subheader("Sync Allotment")
        wait_list = [r for r in req_list if not r.get('bed_no')] if 'req_list' in locals() else []
        if wait_list:
            p_sel = st.selectbox("Select Patient", [r['name'] for r in wait_list])
            b_val = st.text_input("Enter Bed No.")
            if st.button("Finalize & Sync"):
                rid = next(r['ID'] for r in wait_list if r['name'] == p_sel)
                db.collection("bed_requests").document(rid).update({"bed_no": b_val})
                if b_val in all_bed_ids:
                    db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                st.rerun()

# --- 7. VISUAL DASHBOARD ---
if is_live != "LIVE":
    st.error("⚠️ DASHBOARD OFFLINE")
    st.stop()

status_colors = {"VACANT": "#FFFFFF", "RESTRICTED": "#FF0000", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0"}
