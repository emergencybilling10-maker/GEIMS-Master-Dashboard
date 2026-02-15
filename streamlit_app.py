import streamlit as st
import pandas as pd
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

# --- 3. SYSTEM STATE & LIVE DATA ---
status_ref = db.collection("settings").document("dashboard_status")
current_status_doc = status_ref.get()
is_live = current_status_doc.to_dict().get("status", "LIVE") if current_status_doc.exists else "LIVE"

docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}

# --- 4. HEADER & SUGGESTION 2: OCCUPANCY COUNTER ---
st.markdown("<h1 style='text-align: center; color: white;'>Graphic Era Institute of Medical Sciences - GEIMS, Dehradun</h1>", unsafe_allow_html=True)

if is_live == "LIVE":
    total_beds = len(all_bed_ids)
    occupied_beds = sum(1 for b in live_data.values() if b.get('status') in ["ALLOTTED", "BOOKED", "RESTRICTED"])
    vacant_beds = total_beds - occupied_beds
    
    requests_stream = db.collection("bed_requests").stream()
    all_reqs = [r.to_dict() for r in requests_stream]
    waiting_count = sum(1 for r in all_reqs if not r.get('bed_no'))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Occupancy %", f"{round((occupied_beds/total_beds)*100)}%")
    m2.metric("Vacant Private Beds", vacant_beds)
    m3.metric("Waiting Requests", waiting_count)
    m4.metric("Last Data Update", datetime.now().strftime('%H:%M'))
st.divider()

# --- 5. PATIENT BED REQUEST PLATFORM & SUGGESTION 3: EXPORT ---
with st.expander("📋 OPEN PATIENT BED REQUEST FORM"):
    st.subheader("New Shifting Request")
    with st.form("request_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            req_name = st.text_input("NAME")
            req_cat = st.selectbox("CATEGORY", ["ECHS", "TPA", "CGHS CREDIT", "SELF PAY", "CGHS CASH", "ESI", "AYUSHMAN", "ICAR", "UJVN", "UPCL", "ISRO", "BHEL", "ONGC", "OTHER"])
            req_dr = st.text_input("DOCTOR NAME")
        with col2:
            req_from = st.selectbox("REQUEST FROM", ["CCU", "ICU", "WARD", "LR", "SEMI-PRIVATE", "PRIVATE", "OTHER"])
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
                st.rerun()

    st.divider()
    st.subheader("Current Request Status List")
    
    # Suggestion 3: Export to CSV
    if all_reqs:
        df = pd.DataFrame(all_reqs)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Daily Request Report", data=csv, file_name=f"GEIMS_Requests_{datetime.now().strftime('%d_%m')}.csv", mime='text/csv')

    f_col1, f_col2 = st.columns([2, 1])
    search_query = f_col1.text_input("🔍 Search Name", "").lower()
    filter_status = f_col2.selectbox("Filter Status", ["ALL", "WAITING", "DONE"])

    filtered_list = []
    # Pull fresh data for IDs
    requests_full = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    for r in requests_full:
        d = r.to_dict()
        d['ID'] = r.id
        status_val = "DONE" if d.get('bed_no') else "WAITING"
        if (search_query in d.get('name', '').lower()) and (filter_status == "ALL" or filter_status == status_val):
            d['current_status'] = status_val
            filtered_list.append(d)
        
    if filtered_list:
        t_cols = st.columns([0.5, 2, 1.5, 1.5, 1, 1, 2, 1, 1])
        headers = ["S.N", "NAME", "CATEGORY", "DR.NAME", "FROM", "TO", "REMARK", "BED", "STATUS"]
        for col, h in zip(t_cols, headers): col.write(f"**{h}**")
        for idx, r in enumerate(filtered_list):
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1, 1, 2, 1, 1])
            r_cols[0].write(idx + 1)
            r_cols[1].write(r.get('name', '-'))
            r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-'))
            r_cols[4].write(r.get('shift_from', '-'))
            r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-'))
            r_cols[7].write(r.get('bed_no', '-'))
            color = "green" if r['current_status'] == "DONE" else "orange"
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{r['current_status']}</span>", unsafe_allow_html=True)

# --- 6. ADMIN PANEL & SUGGESTION 1: AUTO-SYNC ---
with st.sidebar:
    st.header("🔐 Master Controls")
    bed_pwd = st.text_input("Standard Password", type="password")
    if bed_pwd == "Geims248001":
        st.subheader("Bed Management")
        sel_bed = st.selectbox("Select Bed", all_bed_ids)
        new_stat = st.selectbox("Status", ["VACANT", "RESTRICTED", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE"])
        p_name = st.text_input("Patient Name")
        if st.button("Update Dashboard"):
            db.collection("beds").document(sel_bed).set({"status": new_stat, "patient": p_name})
            st.rerun()
            
        st.divider()
        st.subheader("Process Shifting Request")
        waiting_list = [r for r in filtered_list if r['current_status'] == "WAITING"]
        if waiting_list:
            target_req = st.selectbox("Select Patient", [r['name'] for r in waiting_list])
            assigned_bed = st.text_input("Assign Bed Number")
            if st.button("Finalize Allotment"):
                # SUGGESTION 1: AUTOMATED SYNCING
                # Update Request List
                req_id = next(r['ID'] for r in waiting_list if r['name'] == target_req)
                db.collection("bed_requests").document(req_id).update({"bed_no": assigned_bed})
                # Auto-update Visual Dashboard
                if assigned_bed in all_bed_ids:
                    db.collection("beds").document(assigned_bed).set({"status": "ALLOTTED", "patient": target_req})
                    st.success(f"Synced {target_req} to {assigned_bed}!")
                st.rerun()

    st.divider()
    sys_pwd = st.text_input("System Password", type="password")
    if sys_pwd == "GeimsAdmin99":
        new_mode = st.radio("Mode", ["LIVE", "OFFLINE"], index=0 if is_live == "LIVE" else 1)
        if st.button("Apply"): status_ref.set({"status": new_mode}); st.rerun()
        if st.button("RESET LIST ONLY"):
            for r in db.collection("bed_requests").stream(): r.reference.delete()
            st.rerun()
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            st.rerun()

# --- 7. DASHBOARD DISPLAY ---
if is_live != "LIVE":
    st.error("⚠️ DASHBOARD IS OFFLINE")
    st.stop()

status_colors = {"VACANT": "#FFFFFF", "RESTRICTED": "#FF0000", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0"}

st.title("🏥 GEIMS Live Bed Status")
for wing, beds in bed_structure.items():
    st.subheader(wing)
    cols = st.columns(5)
    for i, bed in enumerate(beds):
        data = live_data.get(bed, {"status": "VACANT", "patient": ""})
        bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
        txt = "white" if data.get('status') in ["ALLOTTED", "RESTRICTED"] else "black"
        with cols[i % 5]:
            st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:10px; border:1px solid #ccc; border-radius:5px; text-align:center; height:100px; margin-bottom:10px;"><div style="font-size:12px; font-weight:bold;">{bed}</div><div style="font-size:10px;">{data.get("status", "VACANT")}</div><div style="font-size:11px; font-style:italic;">{data.get("patient", "")}</div></div>', unsafe_allow_html=True)
    st.divider()
