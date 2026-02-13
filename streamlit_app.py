import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 0. BACKGROUND BRANDING (FIXED) ---
# This adds the GEIMS logo as a subtle watermark background
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url("https://raw.githubusercontent.com/emergencybilling10-maker/geims-master-dashboard/main/geims%20image.jpg");
        background-attachment: fixed;
        background-size: 600px;
        background-repeat: no-repeat;
        background-position: center;
        background-color: rgba(255, 255, 255, 0.95);
        background-blend-mode: overlay;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- 3. ADMIN PANEL ---
with st.sidebar:
    st.header("🔐 Admin Portal")
    pwd = st.text_input("Admin Password", type="password")
    is_admin = (pwd == "Geims248001")
    if is_admin:
        all_ids = [b for w in bed_structure.values() for b in w]
        sel_bed = st.selectbox("Select Bed", all_ids)
        new_stat = st.selectbox("Status", ["VACANT", "RESTRICTED", "TO BE AWARE", "BOOKED", "ALLOTTED", "DISCHARGE", "UNDER MAINTENANCE"])
        p_name = st.text_input("Patient Name")
        if st.button("Update Permanently"):
            db.collection("beds").document(sel_bed).set({"status": new_stat, "patient": p_name})
            st.rerun()

# --- 4. DASHBOARD ---
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
            st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:10px; border:1px solid #ccc; border-radius:5px; text-align:center; height:100px; margin-bottom:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);"><div style="font-size:12px; font-weight:bold;">{bed}</div><div style="font-size:10px;">{data["status"]}</div><div style="font-size:11px; font-style:italic;">{data["patient"]}</div></div>', unsafe_allow_html=True)
    st.divider()
