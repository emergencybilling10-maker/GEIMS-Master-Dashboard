import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 1. SECURE DATABASE CONNECTION (OPTIMIZED) ---
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
if db:
    status_ref = db.collection("settings").document("dashboard_status")
    status_doc = status_ref.get()
    is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"

    docs = db.collection("beds").stream()
    live_data = {doc.id: doc.to_dict() for doc in docs}

    reqs_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
    req_list = []
    for r in reqs_stream:
        d = r.to_dict(); d['ID'] = r.id; req_list.append(d)
else:
    st.error("Database connection failed.")
    st.stop()

# --- 4. HEADER & DATE ---
tz = pytz.timezone('Asia/Kolkata')
today_date = datetime.now(tz).strftime('%d/%m/%Y')
st.markdown("<h1 style='text-align: center;'>🏥 GEIMS Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date}</b></p>", unsafe_allow_html=True)

# --- 5. PATIENT BED REQUEST PLATFORM ---
with st.expander("📋 MANAGE PATIENT REQUESTS", expanded=True):
    # WARD STATISTICS BAR
    pending_count = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted_count = sum(1 for r in req_list if r.get('bed_no') != "")
    cancelled_count = sum(1 for r in req_list if r.get('status') == "CANCELLED")

    st.subheader("📊 Shifting Statistics")
    stat_cols = st.columns(3)
    stat_cols[0].metric("Pending Requests", pending_count)
    stat_cols[1].metric("Allotted (Done)", allotted_count)
    stat_cols[2].metric("Cancelled", cancelled_count)
    st.divider()

    with st.form("new_req", clear_on_submit=True):
        st.subheader("New Shifting Request Entry")
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
                    "timestamp": datetime.now(tz), "name": p_name, "category": p_cat,
                    "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                    "remark": rem, "bed_no": "", "status": "WAITING", "date": today_date
                })
                st.rerun()

    if req_list:
        st.divider()
        st.subheader("Shifting Request Status List")
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["S.N", "NAME", "CATEGORY", "DOCTOR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        
        for idx, r in enumerate(req_list):
            b_no = r.get('bed_no', '')
            status = r.get('status', 'WAITING')
            if b_no: status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1)
            r_cols[1].write(r.get('name', '-'))
            r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-'))
            r_cols[4].write(r.get('shift_from', '-'))
            r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-'))
            r_cols[7].write(b_no if b_no else "-")
            
            color = "green" if status == "DONE" else ("red" if status == "CANCELLED" else "orange")
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{status}</span>", unsafe_allow_html=True)

            if status == "DONE":
                # PROFESSIONAL A5 RECEIPT FORMAT
                receipt_text = f"""
====================================
      GEIMS BED ALLOTMENT SLIP
      (A5 DOCUMENT FORMAT)
====================================
DATE: {today_date}
PATIENT NAME: {r['name']}
CATEGORY: {r.get('category', '-')}
ADMITTED UNDER: {r.get('dr_name', '-')}

------------------------------------
SHIFTING FROM: {r.get('shift_from', '-')}
SHIFTING TO:   {r.get('shift_to', '-')}
------------------------------------
ALLOTTED BED:  {b_no}
REMARK: {r.get('remark', '-')}
------------------------------------

Authorized by: GEIMS Master Admin
Note: This slip is valid for 2 hours.
====================================
"""
                r_cols[9].download_button("🖨️ Receipt (A5)", data=receipt_text, file_name=f"GEIMS_Receipt_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- 6. UNIFIED ADMIN SIDEBAR CONTROL ---
show_dashboard = False 
with st.sidebar:
    st.header("🛡️ Admin Control Panel")
    admin_pwd = st.text_input("Enter Admin Password", type="password")
    
    if admin_pwd == "GeimsAdmin99":
        st.success("Authorized: Full Access")
        show_dashboard = True 

        # Modification Tools
        st.divider()
        st.subheader("📝 Entry Modification")
        if req_list:
            target = st.selectbox("Select Patient to Modify", [r['name'] for r in req_list], key="sidebar_mod")
            action = st.radio("Action", ["Edit Remark", "Mark as CANCELLED", "Delete Entry"], horizontal=True)
            new_val = st.text_input("New Remark (if editing)")
            if st.button("Confirm Action"):
                r_id = next(r['ID'] for r in req_list if r['name'] == target)
                if action == "Delete Entry": db.collection("bed_requests").document(r_id).delete()
                elif action == "Mark as CANCELLED": db.collection("bed_requests").document(r_id).update({"status": "CANCELLED", "bed_no": ""})
                else: db.collection("bed_requests").document(r_id).update({"remark": new_val})
                st.rerun()
        
        # Allotment Tools
        st.divider()
        st.subheader("🔑 Allotment Tools")
        waiting = [r for r in req_list if not r.get('bed_no') and r.get('status') == "WAITING"]
        if waiting:
            p_sel = st.selectbox("Assign Bed to Patient", [r['name'] for r in waiting])
            b_val = st.text_input("Enter Bed No.")
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in waiting if r['name'] == p_sel)
                db.collection("bed_requests").document(r_id).update({"bed_no": b_val, "status": "DONE"})
                if b_val in all_bed_ids:
                    db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                st.rerun()
        
        # Manual Updates
        st.divider()
        st.subheader("⚙️ Manual Bed Update")
        man_bed = st.selectbox("Select Bed ID", all_bed_ids)
        man_stat = st.selectbox("Update Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE", "RESTRICTED"])
        man_name = st.text_input("Patient Name (Manual)")
        if st.button("Apply Manual Update"):
            db.collection("beds").document(man_bed).set({"status": man_stat, "patient": man_name})
            st.rerun()

        st.divider()
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.rerun()
    elif admin_pwd != "":
        st.error("Incorrect Password")

# --- 7. VISUAL DASHBOARD ---
if show_dashboard:
    if is_live != "LIVE": st.error("⚠️ SYSTEM OFFLINE"); st.stop()
    status_colors = {"VACANT": "#FFFFFF", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0", "RESTRICTED": "#FF0000"}
    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing)
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
            txt = "white" if data.get('status') in ["ALLOTTED", "RESTRICTED"] else "black"
            with cols[i % 5]:
                st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:85px; font-size:11px;"><b>{bed}</b><br><span style="font-size:10px; font-weight:bold;">{data.get("status", "VACANT")}</span><br><i style="font-size:10px;">{data.get("patient", "")}</i></div>', unsafe_allow_html=True)
        st.divider()
else:
    st.info("🔒 Visual Bed Dashboard restricted. Enter Admin Password in the sidebar.")
