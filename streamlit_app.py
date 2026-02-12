import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json

# Page Config
st.set_page_config(page_title="GEIMS Bed Management", layout="wide")

# --- DATABASE CONNECTION ---
# This looks for the 'Secret Key' you paste in Streamlit Settings
if "textkey" in st.secrets:
    try:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        db = firestore.Client(credentials=creds)
    except Exception as e:
        st.error(f"Database Secret Error: {e}")
        st.stop()
else:
    st.warning("Admin: Please add the Firestore JSON key to Streamlit Secrets.")
    st.stop()

# --- ADMIN SECURITY ---
with st.sidebar:
    st.header("🔐 Admin Portal")
    pwd = st.text_input("Enter Password to Edit", type="password")
    is_admin = (pwd == "Geims248001")
    
    if is_admin:
        st.success("Authorized Access")
    else:
        st.info("View-Only Mode")

# --- DATABASE FUNCTIONS ---
def update_bed(bed_id, status, patient):
    db.collection("beds").document(bed_id).set({
        "status": status,
        "patient": patient
    })

def get_all_beds():
    docs = db.collection("beds").stream()
    return {doc.id: doc.to_dict() for doc in docs}

# Load Live Data
live_data = get_all_beds()

# --- MAIN INTERFACE ---
st.title("🏥 GEIMS Live Bed Status")

# Add Admin Controls if password is correct
if is_admin:
    with st.expander("Update Bed Status"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bed_to_edit = st.text_input("Enter Bed ID (e.g., F-D-9052)")
        with col2:
            new_stat = st.selectbox("Status", ["VACANT", "RESTRICTED", "TO BE AWARE", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE"])
        with col3:
            p_name = st.text_input("Patient Name (Leave blank to remove)")
        
        if st.button("Save to Database"):
            update_bed(bed_to_edit, new_stat, p_name)
            st.rerun()

# --- DASHBOARD DISPLAY ---
# (Logic to display your grid based on the live_data dictionary)
