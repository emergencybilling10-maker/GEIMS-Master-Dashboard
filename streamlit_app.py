import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

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

# --- 3. LIVE DATA FETCH ---
docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}

# --- 4. HEADER & DATE ---
tz = pytz.timezone('Asia/Kolkata')
today_date = datetime.now(tz).strftime('%d/%m/%Y')
st.markdown("<h1 style='text-align: center;'>🏥 GEIMS Bed Management System</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date}</b></p>", unsafe_allow_html=True)

# --- 5. PATIENT BED REQUEST PLATFORM (Public) ---
st.subheader("📋 Patient Shifting Requests")
with st.form("new_req", clear_on_submit=True):
    c1, c2 = st.columns(2)
    p_name = c1.text_input("PATIENT NAME")
    p_cat = c1.selectbox("CATEGORY", ["ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "SELF PAY", "ICAR", "AYUSHMAN", "OTHER"])
    dr_name = c1.text_input("ADMITTED UNDER DOCTOR")
    p_fr = c2.selectbox("SHIFT FROM", ["CCU", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
    p_to = c2.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
    rem = c2.text_input("REMARK")
    if st.form_submit_button("Submit Request"):
        if p_name:
            db.collection("bed_requests").add({
                "timestamp": datetime.now(), "name": p_name, "category": p_cat,
                "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                "remark": rem, "bed_no": "", "date": today_date
            })
            st.rerun()

st.divider()

# FETCH REQUESTS
reqs_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()
req_list = []
for r in reqs_stream:
    d = r.to_dict(); d['ID'] = r.id; req_list.append(d)

if req_list:
    # PUBLIC QUICK EDIT (Visible to all)
    st.subheader("📝 Quick Update Remark")
    edit_col1, edit_col2 = st.columns([2, 2])
    target_edit = edit_col1.selectbox("Select Patient", [r['name'] for r in req_list], key="public_edit")
    new_remark_val = edit_col2.text_input("Update Remark")
    if st.button("Update Remark"):
        r_id = next(r['ID'] for r in req_list if r['name'] == target_edit)
        db.collection("bed_requests").document(r_id).update({"remark": new_remark_val})
        st.success(f"Remark updated.")
        st.rerun()

    st.divider()
    st.subheader("Shifting Request Status List")
    h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
    headers = ["S.N", "NAME", "CATEGORY", "DOCTOR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
    for col, h in zip(h_cols, headers): col.write(f"**{h}**")
    
    for idx, r in enumerate(req_list):
        b_no = r.get('bed_no', '')
        status = "DONE" if b_no else "WAITING"
        r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-'))
        r_cols[2].write(r.get('category', '-')); r_cols[3].write(r.get('dr_name', '-'))
        r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
        r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
        color = "green" if status == "DONE" else "orange"
        r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{status}</span>", unsafe_allow_html=True)
        if status == "DONE":
            receipt = f"Patient: {r['name']}\nDoctor: {r.get('dr_name', '-')}\nFrom: {r['shift_from']}\nTo: {r['shift_to']}\nBed No: {b_no}\nValid: {today_date}"
            r_cols[9].download_button("🖨️ Receipt", data=receipt, file_name=f"Receipt_{r['name']}.txt", key=f"print_{r['ID']}")

# --- 6. ADMIN PRIVATE AREA (Sidebar) ---
with st.sidebar:
    st.header("🔐 Admin Authorization")
    pwd = st.text_input("Enter Password to View Beds", type="password")
    
    if pwd == "Geims248001":
        st.success("Authorized: Bed Viewer Active")
        # --- HIDDEN BED DASHBOARD (Moves here) ---
        st.divider()
        st.subheader("🏥 Live Bed Status")
        status_colors = {"VACANT": "#FFFFFF", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0", "RESTRICTED": "#FF0000"}
        for wing, beds in bed_structure.items():
            st.write(f"**{wing}**")
            for bed in beds:
                data = live_data.get(bed, {"status": "VACANT", "patient": ""})
                curr_stat = data.get('status', 'VACANT')
                bg = status_colors.get(curr_stat, "#FFFFFF")
                st.markdown(f'<div style="background-color:{bg}; padding:3px; border-radius:3px; font-size:10px; color:black; margin-bottom:2px;">{bed}: {curr_stat} ({data.get("patient", "")})</div>', unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Sync & Allot")
        waiting = [r for r in req_list if not r.get('bed_no')]
        if waiting:
            p_sel = st.selectbox("Select Patient", [r['name'] for r in waiting])
            b_val = st.text_input("Assign Bed No.")
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in req_list if r['name'] == p_sel)
                db.collection("bed_requests").document(r_id).update({"bed_no": b_val})
                if b_val in all_bed_ids:
                    db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                st.rerun()

    elif pwd == "GeimsAdmin99":
        st.success("Authorized: Master Admin Active")
        # --- SAME HIDDEN VIEW FOR MASTER ADMIN ---
        st.subheader("🏥 Live Bed Status")
        for wing, beds in bed_structure.items():
            st.write(f"**{wing}**")
            for bed in beds:
                data = live_data.get(bed, {"status": "VACANT", "patient": ""})
                st.write(f"{bed}: {data.get('status')} ({data.get('patient', '')})")

        st.divider()
        st.subheader("🗑️ Delete Request")
        if req_list:
            target_del = st.selectbox("Select Patient to Remove", [r['name'] for r in req_list])
            if st.button("Delete Selected Entry"):
                r_id = next(r['ID'] for r in req_list if r['name'] == target_del)
                db.collection("bed_requests").document(r_id).delete()
                st.rerun()

        st.divider()
        st.error("⚠️ DATA RESET")
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.rerun()
        if st.button("CLEAR REQUEST LIST"):
            for r in db.collection("bed_requests").stream(): r.reference.delete()
            st.rerun()
    else:
        st.info("🔒 Visual Bed Status is restricted to Admins. Enter password to unlock.")
