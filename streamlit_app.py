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

# --- 2. FULL BED LIST (Fixed) ---
bed_structure = {
    "Eighth Floor - B Wing": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "Ninth Floor - A Wing": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "Ninth Floor - B Wing": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "Ninth Floor - C Wing": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "Ninth Floor - F Wing": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
}
all_bed_ids = [b for w in bed_structure.values() for b in w]

# --- 3. SYSTEM STATE & HEADER ---
status_ref = db.collection("settings").document("dashboard_status")
current_status_doc = status_ref.get()
is_live = current_status_doc.to_dict().get("status", "LIVE") == "LIVE" if current_status_doc.exists else True

st.markdown("<h1 style='text-align: center; color: white;'>Graphic Era Institute of Medical Sciences - GEIMS, Dehradun</h1>", unsafe_allow_html=True)

# --- 4. PATIENT BED REQUEST PLATFORM (EXCEL REFERENCE) ---
with st.expander("📋 OPEN PATIENT BED REQUEST FORM (Click to Pop Up/Minimize)"):
    st.subheader("New Bed Request Details")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        req_name = st.text_input("Patient Name")
        req_cat = st.selectbox("Category", ["General", "Private", "Semi-Private", "Deluxe"])
        req_dr = st.text_input("Doctor Name")
    with col2:
        req_from = st.text_input("Shift From")
        req_to = st.text_input("Shift To")
        req_wing = st.selectbox("Wing", list(bed_structure.keys()))
    with col3:
        req_status = st.selectbox("Request Status", ["PENDING", "APPROVED", "CANCELLED"])
        req_remark = st.text_area("Remark")
    
    if st.button("Submit Request"):
        if req_name:
            db.collection("bed_requests").add({
                "timestamp": datetime.now(),
                "name": req_name,
                "category": req_cat,
                "dr_name": req_dr,
                "shift_from": req_from,
                "shift_to": req_to,
                "remark": req_remark,
                "status": req_status,
                "wing": req_wing
            })
            st.success(f"Request for {req_name} submitted successfully!")
        else:
            st.error("Please enter a Patient Name.")

    st.divider()
    st.subheader("Recent Bed Requests")
    req_docs = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
    for r in req_docs:
        r_data = r.to_dict()
        st.info(f"**{r_data['name']}** | {r_data['dr_name']} | {r_data['shift_from']} ➔ {r_data['shift_to']} | Status: {r_data['status']}")

# --- 5. ADMIN PANEL ---
with st.sidebar:
    st.header("🔐 Master Controls")
    
    # 1. BED UPDATE PASSWORD
    bed_pwd = st.text_input("Bed Update Password", type="password")
    if (bed_pwd == "Geims248001"):
        st.subheader("Bed Management")
        sel_bed = st.selectbox("Select Bed", all_bed_ids)
        new_stat = st.selectbox("Status", ["VACANT", "RESTRICTED", "TO BE AWARE", "BOOKED", "ALLOTTED", "DISCHARGE", "UNDER MAINTENANCE"])
        p_name = st.text_input("Update Patient Name")
        if st.button("Update Bed Permanently"):
            db.collection("beds").document(sel_bed).set({"status": new_stat, "patient": p_name})
            st.rerun()

    st.divider()
    
    # 2. SYSTEM STATUS & RESET PASSWORD
    sys_pwd = st.text_input("System Admin Password", type="password")
    if (sys_pwd == "GeimsAdmin99"):
        st.subheader("⚙️ System Controls")
        new_mode = st.radio("Toggle Dashboard Mode", ["LIVE", "OFFLINE"], index=0 if is_live else 1)
        if st.button("Apply Mode Change"):
            status_ref.set({"status": new_mode})
            st.rerun()
        if st.button("RESET ALL BEDS (VACANT)"):
            batch = db.batch()
            for bed_id in all_bed_ids:
                doc_ref = db.collection("beds").document(bed_id)
                batch.set(doc_ref, {"status": "VACANT", "patient": ""})
            batch.commit()
            st.rerun()

# --- 6. DASHBOARD DISPLAY ---
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
