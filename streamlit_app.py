import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 1. SECURE DATABASE CONNECTION ---
if "textkey" in st.secrets:
    try:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        db = firestore.Client(credentials=creds)
    except Exception as e:
        st.error(f"Secret Key Error: {e}")
        st.stop()
else:
    st.warning("Admin: Please add the Firestore JSON key to Streamlit Secrets.")
    st.stop()

# --- 2. FULL BED LIST ---
bed_structure = {
    "Eighth Floor - B Wing": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "Ninth Floor - A Wing": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "Ninth Floor - B Wing": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "Ninth Floor - C Wing": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "Ninth Floor - F Wing": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
}
all_bed_ids = [b for w in bed_structure.values() for b in w]

# --- 3. SYSTEM STATE ---
status_ref = db.collection("settings").document("dashboard_status")
current_status_doc = status_ref.get()
is_live = current_status_doc.to_dict().get("status", "LIVE") == "LIVE" if current_status_doc.exists else True

# --- 4. HEADER ---
st.markdown("<h1 style='text-align: center; color: white;'>Graphic Era Institute of Medical Sciences - GEIMS, Dehradun</h1>", unsafe_allow_html=True)
st.markdown(f"<h4 style='text-align: center; color: gray;'>Date: {datetime.now().strftime('%d/%m/%Y')}</h4>", unsafe_allow_html=True)

# --- 5. PATIENT BED REQUEST PLATFORM (POP-UP) ---
with st.expander("📋 OPEN PATIENT BED REQUEST FORM (Click to Pop Up/Minimize)"):
    st.subheader("New Shifting Request")
    
    with st.form("request_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            req_name = st.text_input("NAME (Patient Name)")
            req_cat = st.selectbox("CATEGORY", ["ECHS", "TPA", "CGHS CREDIT", "SELF PAY", "CGHS CASH", "ESI", "AYUSHMAN", "ICAR", "UJVN", "UPCL", "ISRO", "BHEL", "ONGC", "OTHER"])
            req_dr = st.text_input("DOCTOR NAME")
        with col2:
            req_from = st.selectbox("REQUEST TO SHIFT FROM", ["CCU", "ICU", "WARD", "LR", "SEMI-PRIVATE", "PRIVATE", "OTHER"])
            req_to = st.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            req_remark = st.text_input("REMARK")
            
        if st.form_submit_button("Submit Bed Request"):
            if req_name:
                db.collection("bed_requests").add({
                    "date": datetime.now().strftime('%d/%m/%Y'),
                    "timestamp": datetime.now(),
                    "name": req_name,
                    "category": req_cat,
                    "dr_name": req_dr,
                    "shift_from": req_from,
                    "shift_to": req_to,
                    "remark": req_remark,
                    "bed_no": ""
                })
                st.success("Request Submitted Successfully!")
                st.rerun()

    st.divider()
    
    # SEARCH AND FILTER SECTION
    st.subheader("Current Request Status List")
    f_col1, f_col2 = st.columns([2, 1])
    search_query = f_col1.text_input("🔍 Search Patient Name", "").lower()
    filter_status = f_col2.selectbox("Filter Status", ["ALL", "WAITING", "DONE"])

    requests = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    req_list = []
    for r in requests:
        d = r.to_dict()
        d['ID'] = r.id
        status_val = "DONE" if d['bed_no'] else "WAITING"
        if (search_query in d['name'].lower()) and (filter_status == "ALL" or filter_status == status_val):
            req_list.append(d)
        
    if req_list:
        t_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1])
        headers = ["S.N", "NAME", "CATEGORY", "DR.NAME", "FROM", "TO", "REMARK", "BED", "STATUS"]
        for col, h in zip(t_cols, headers): col.write(f"**{h}**")
        
        for idx, r in enumerate(req_list):
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1])
            r_cols[0].write(idx + 1)
            r_cols[1].write(r['name'])
            r_cols[2].write(r['category'])
            r_cols[3].write(r['dr_name'])
            r_cols[4].write(r['shift_from'])
            r_cols[5].write(r['shift_to'])
            r_cols[6].write(r['remark'])
            r_cols[7].write(r['bed_no'] if r['bed_no'] else "-")
            status_text = "DONE" if r['bed_no'] else "WAITING"
            status_color = "green" if status_text == "DONE" else "orange"
            r_cols[8].markdown(f"<span style='color:{status_color}; font-weight:bold;'>{status_text}</span>", unsafe_allow_html=True)
    else:
        st.info("No matching requests found.")

# --- 6. ADMIN PANEL ---
with st.sidebar:
    st.header("🔐 Master Controls")
    
    # 1. BED UPDATE PASSWORD
    bed_pwd = st.text_input("Bed Update Password", type="password")
    if (bed_pwd == "Geims248001"):
        st.subheader("Bed Management")
        sel_bed = st.selectbox("Select Dashboard Bed", all_bed_ids)
        new_stat = st.selectbox("Status", ["VACANT", "RESTRICTED", "TO BE AWARE", "BOOKED", "ALLOTTED", "DISCHARGE", "UNDER MAINTENANCE"])
        p_name = st.text_input("Patient Name for Dashboard")
        if st.button("Update Dashboard Bed"):
            db.collection("beds").document(sel_bed).set({"status": new_stat, "patient": p_name})
            st.rerun()
            
        st.divider()
        st.subheader("Process Bed Request")
        waiting_reqs = [r['name'] for r in req_list if not r['bed_no']]
        if waiting_reqs:
            target_req = st.selectbox("Select Patient to Allot", waiting_reqs)
            assigned_bed = st.text_input("Enter Allotted Bed No.")
            if st.button("Complete Allotment"):
                req_id = next(item['ID'] for item in req_list if item["name"] == target_req)
                db.collection("bed_requests").document(req_id).update({"bed_no": assigned_bed})
                st.success(f"Bed {assigned_bed} allotted.")
                st.rerun()

    st.divider()
    
    # 2. SYSTEM STATUS & RESET PASSWORD
    sys_pwd = st.text_input("System Admin Password", type="password")
    if (sys_pwd == "GeimsAdmin99"):
        st.subheader("⚙️ System Controls")
        new_mode = st.radio("System Mode", ["LIVE", "OFFLINE"], index=0 if is_live else 1)
        if st.button("Apply Mode Change"):
            status_ref.set({"status": new_mode})
            st.rerun()
        if st.button("RESET ALL BED REQUESTS"):
            req_batch = db.batch()
            for r in db.collection("bed_requests").stream(): req_batch.delete(r.reference)
            req_batch.commit()
            st.rerun()
        if st.button("RESET ALL DASHBOARD BEDS"):
            batch = db.batch()
            for b in all_bed_ids: batch.set(db.collection("beds").document(b), {"status": "VACANT", "patient": ""})
            batch.commit()
            st.rerun()

# --- 7. DASHBOARD DISPLAY ---
if not is_live:
    st.error("⚠️ DASHBOARD IS CURRENTLY OFFLINE FOR MAINTENANCE")
    st.stop()

docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}
status_colors = {"VACANT": "#FFFFFF", "RESTRICTED": "#FF0000", "TO BE AWARE": "#FFFF00", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "UNDER MAINTENANCE": "#E0E0E0"}

st.title("🏥 GEIMS Live Bed Status")
for wing, beds in bed_structure.items():
    st.subheader(wing)
    cols = st.columns(5)
    for i, bed in enumerate(beds):
        data = live_data.get(bed, {"status": "VACANT", "patient": ""})
        bg = status_colors.get(data['status'], "#FFFFFF")
        txt = "white" if data['status'] in ["ALLOTTED", "RESTRICTED"] else "black"
        with cols[i % 5]:
            st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:10px; border:1px solid #ccc; border-radius:5px; text-align:center; height:100px; margin-bottom:10px;"><div style="font-size:12px; font-weight:bold;">{bed}</div><div style="font-size:10px;">{data["status"]}</div><div style="font-size:11px; font-style:italic;">{data["patient"]}</div></div>', unsafe_allow_html=True)
    st.divider()
