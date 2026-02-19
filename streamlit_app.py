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
status_ref = db.collection("settings").document("dashboard_status")
status_doc = status_ref.get()
is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"

docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}

# --- 4. HEADER & DATE ---
tz = pytz.timezone('Asia/Kolkata')
today_date = datetime.now(tz).strftime('%d/%m/%Y')
st.markdown("<h1 style='text-align: center;'>🏥 GEIMS Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date}</b></p>", unsafe_allow_html=True)

# --- 5. PATIENT BED REQUEST PLATFORM ---
with st.expander("📋 MANAGE PATIENT REQUESTS"):
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
                    "timestamp": datetime.now(), "name": p_name, "category": p_cat,
                    "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                    "remark": rem, "bed_no": "", "status": "WAITING", "date": today_date
                })
                st.rerun()

    st.divider()
    reqs_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()
    req_list = []
    for r in reqs_stream:
        d = r.to_dict(); d['ID'] = r.id; req_list.append(d)

    if req_list:
        st.subheader("📝 Edit, Cancel or Remove Entry")
        e_col1, e_col2 = st.columns(2)
        target = e_col1.selectbox("Select Patient to Modify", [r['name'] for r in req_list], key="edit_sel")
        # ADDED CANCELLED OPTION IN THE ACTIONS
        action = e_col1.radio("Select Action", ["Edit Remark", "Mark as CANCELLED", "Delete Entry"], horizontal=True)
        new_val = e_col2.text_input("New Remark (Leave blank for delete/cancel)")
        
        if st.button("Confirm Modification"):
            r_id = next(r['ID'] for r in req_list if r['name'] == target)
            if action == "Delete Entry":
                db.collection("bed_requests").document(r_id).delete()
            elif action == "Mark as CANCELLED":
                db.collection("bed_requests").document(r_id).update({"status": "CANCELLED", "bed_no": ""})
            else:
                db.collection("bed_requests").document(r_id).update({"remark": new_val})
            st.rerun()

        st.divider()
        st.subheader("Shifting Request Status List")
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["S.N", "NAME", "CATEGORY", "DOCTOR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        
        for idx, r in enumerate(req_list):
            b_no = r.get('bed_no', '')
            # LOGIC FOR CANCELLED STATUS DISPLAY
            current_status = r.get('status', 'WAITING')
            if b_no:
                current_status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1)
            r_cols[1].write(r.get('name', '-'))
            r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-'))
            r_cols[4].write(r.get('shift_from', '-'))
            r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-'))
            r_cols[7].write(b_no if b_no else "-")
            
            # COLOR CODING FOR CANCELLED STATUS
            if current_status == "DONE":
                color = "green"
            elif current_status == "CANCELLED":
                color = "red"
            else:
                color = "orange"
                
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{current_status}</span>", unsafe_allow_html=True)

            if current_status == "DONE":
                receipt_text = f"--- GEIMS BED ALLOTMENT RECEIPT ---\nPatient: {r['name']}\nDoctor: {r.get('dr_name', '-')}\nFrom: {r['shift_from']}\nTo: {r['shift_to']}\nBed No: {b_no}\nNote: Valid for {today_date} only."
                r_cols[9].download_button("🖨️ Receipt", data=receipt_text, file_name=f"Receipt_{r['name']}.txt", key=f"print_{r['ID']}")

# --- 6. SEPARATE SIDEBAR CONTROLS ---
show_dashboard = False 

with st.sidebar:
    st.header("🔑 Bed Allotment Control")
    pwd1 = st.text_input("Allotment Password", type="password", key="pwd1")
    if pwd1 == "Geims248001":
        st.info("Authorized: Manual & List Allotment")
        waiting = [r for r in req_list if not r.get('bed_no') and r.get('status') != "CANCELLED"] if 'req_list' in locals() else []
        if waiting:
            st.subheader("Process List Allotment")
            p_sel = st.selectbox("Select Patient", [r['name'] for r in waiting])
            b_val = st.text_input("Assign Bed No.")
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in waiting if r['name'] == p_sel)
                db.collection("bed_requests").document(r_id).update({"bed_no": b_val, "status": "DONE"})
                if b_val in all_bed_ids:
                    db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                st.rerun()
        
        st.divider()
        st.subheader("Manual Bed Update")
        man_bed = st.selectbox("Select Bed ID", all_bed_ids)
        man_stat = st.selectbox("Update Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE", "RESTRICTED"])
        man_name = st.text_input("Patient Name (Manual)")
        if st.button("Apply Manual Update"):
            db.collection("beds").document(man_bed).set({"status": man_stat, "patient": man_name})
            st.rerun()

    st.divider()
    st.header("🛡️ Master Admin Control")
    pwd2 = st.text_input("Admin Password", type="password", key="pwd2")
    if pwd2 == "GeimsAdmin99":
        st.info("Authorized: Master Admin Access")
        show_dashboard = True 
        
        st.subheader("Dashboard Mode")
        new_mode = st.radio("System Status", ["LIVE", "OFFLINE"], index=0 if is_live == "LIVE" else 1)
        if st.button("Save System Status"):
            status_ref.set({"status": new_mode})
            st.rerun()
        
        st.divider()
        st.error("⚠️ DATA RESET TOOLS")
        
        if st.button("RESET ALL BEDS TO VACANT"):
            for b in all_bed_ids:
                db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.success("All Dashboard Beds Cleared.")
            st.rerun()
            
        if st.button("CLEAR PATIENT REQUEST LIST"):
            for r in db.collection("bed_requests").stream():
                r.reference.delete()
            st.success("Request History Deleted.")
            st.rerun()

# --- 7. VISUAL DASHBOARD ---
if show_dashboard:
    if is_live != "LIVE":
        st.error("⚠️ SYSTEM OFFLINE BY ADMIN ANUJ GILL"); st.stop()

    status_colors = {"VACANT": "#FFFFFF", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0", "RESTRICTED": "#FF0000"}

    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing)
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            current_status = data.get('status', 'VACANT')
            bg = status_colors.get(current_status, "#FFFFFF")
            txt = "white" if current_status in ["ALLOTTED", "RESTRICTED"] else "black"
            with cols[i % 5]:
                st.markdown(f'''
                    <div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:85px; font-size:11px;">
                        <b>{bed}</b><br>
                        <span style="font-size:10px; font-weight:bold;">{current_status}</span><br>
                        <i style="font-size:10px;">{data.get("patient", "")}</i>
                    </div>
                ''', unsafe_allow_html=True)
        st.divider()
else:
    st.info("🔒 Visual Bed Dashboard is restricted to Master Admin access only.")
