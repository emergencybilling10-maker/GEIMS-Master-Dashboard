import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime

# Page Config - Stripped to the bone for speed
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 1. DIRECT DATABASE CONNECTION (NO CACHING) ---
# We are removing @st.cache_resource to clear out old "stuck" data
if "textkey" in st.secrets:
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds)
else:
    st.error("Secrets not found. Please check Streamlit Cloud settings.")
    st.stop()

# --- 2. BED STRUCTURE ---
bed_structure = {
    "Eighth Floor - B Wing": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "Ninth Floor - A Wing": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "Ninth Floor - B Wing": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "Ninth Floor - C Wing": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "Ninth Floor - F Wing": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
}
all_bed_ids = [b for w in bed_structure.values() for b in w]

# --- 3. LIVE BED DATA ---
# Fetching only the current bed status (Smallest possible data load)
docs = db.collection("beds").stream()
live_data = {doc.id: doc.to_dict() for doc in docs}

# --- 4. HEADER ---
st.title("🏥 GEIMS Master Bed Tracker (Reset Mode)")

# --- 5. ADMIN CONTROLS (EMERGENCY DATA CLEARING) ---
with st.sidebar:
    st.header("🔐 Emergency Tools")
    pwd = st.text_input("Password", type="password")
    
    if pwd == "GeimsAdmin99":
        st.error("DANGER ZONE")
        if st.button("DELETE ALL REQUEST HISTORY"):
            # This wipes the historical data that is causing the app to hang.
            for r in db.collection("bed_requests").stream():
                r.reference.delete()
            st.success("History Purged. App should load faster now.")
            st.rerun()

    if pwd == "Geims248001":
        st.subheader("Manual Bed Update")
        sel_bed = st.selectbox("Bed No.", all_bed_ids)
        new_stat = st.selectbox("Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE"])
        p_name = st.text_input("Patient Name")
        if st.button("Update"):
            db.collection("beds").document(sel_bed).set({"status": new_stat, "patient": p_name})
            st.rerun()

# --- 6. BED GRID ---
status_colors = {"VACANT": "#FFFFFF", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6"}

st.header("Bed Status Grid")
for wing, beds in bed_structure.items():
    st.subheader(wing)
    cols = st.columns(5)
    for i, bed in enumerate(beds):
        data = live_data.get(bed, {"status": "VACANT", "patient": ""})
        bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
        txt = "white" if data.get('status') == "ALLOTTED" else "black"
        with cols[i % 5]:
            st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:60px; font-size:10px;"><b>{bed}</b><br>{data.get("patient", "")}</div>', unsafe_allow_html=True)
    st.divider()
