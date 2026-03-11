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

# --- 2. QUOTA SAVING DATA FETCH ---
# This section uses Session State to avoid repeated database hits
if db:
    try:
        if 'last_fetch' not in st.session_state or (datetime.now() - st.session_state.last_fetch).seconds > 300:
            # Only fetch from Firebase once every 5 minutes to save quota
            st.session_state.status_doc = db.collection("settings").document("dashboard_status").get().to_dict()
            
            beds_docs = db.collection("beds").stream()
            st.session_state.live_data = {doc.id: doc.to_dict() for doc in beds_docs}

            reqs_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.ASCENDING).limit(30).stream()
            st.session_state.req_list = [r.to_dict() | {'ID': r.id} for r in reqs_stream]
            
            book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).limit(15).stream()
            st.session_state.book_list = [b.to_dict() | {'ID': b.id} for b in book_stream]
            
            st.session_state.last_fetch = datetime.now()

        # Local variables for the rest of the app
        is_live = st.session_state.status_doc.get("status", "LIVE") if st.session_state.status_doc else "LIVE"
        live_data = st.session_state.live_data
        req_list = st.session_state.req_list
        book_list = st.session_state.book_list

    except Exception as e:
        st.error("Firebase Daily Quota Exceeded. The app will resume once your Spark Plan resets (approx. 1:30 PM IST).")
        st.stop()
else:
    st.error("Database connection failed.")
    st.stop()

# --- 3. HEADER & ALERTS ---
tz = pytz.timezone('Asia/Kolkata')
today_date_str = datetime.now(tz).strftime('%d/%m/%Y')
today_iso = datetime.now(tz).strftime('%Y-%m-%d')

st.markdown("<h1 style='text-align: center;'>GEIMS Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.button("🔄 Refresh Data (Manual)") # Manual refresh button to give user control

# Today's Booking Alert
alerts = [b for b in book_list if b['book_date'] == today_iso]
for a in alerts:
    st.markdown(f"""
        <div style="background-color: #FFEBEE; border: 2px solid #FF5252; padding: 10px; border-radius: 5px; margin-bottom: 10px; animation: blinker 1.5s linear infinite;">
            <span style="color: #D32F2F; font-weight: bold;">🚨 TODAY'S BOOKING ALERT:</span> 
            <b>{a['name']}</b> (UHID: {a.get('uhid','-')}) - Dr. {a.get('dr','-')}
        </div>
        <style> @keyframes blinker {{ 50% {{ opacity: 0.4; }} }} </style>
    """, unsafe_allow_html=True)

# --- 4. PATIENT REQUEST PLATFORM ---
with st.expander("📋 MANAGE PATIENT REQUESTS", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('bed_no') != "")
    
    s1, s2 = st.columns(2)
    s1.metric("Pending", pending); s2.metric("Done", allotted)

    with st.form("new_req", clear_on_submit=True):
        st.subheader("New Shifting Request Entry")
        c1, c2 = st.columns(2)
        p_name = c1.text_input("PATIENT NAME")
        p_cat = c1.selectbox("CATEGORY", ["SELF PAY", "ECHS", "CGHS", "TPA", "OTHER"])
        dr_name = c1.text_input("DOCTOR")
        p_fr = c2.selectbox("FROM", ["ER", "ICU", "WARD", "OT", "OTHER"])
        p_to = c2.selectbox("TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
        if st.form_submit_button("Submit Request"):
            if p_name:
                db.collection("bed_requests").add({
                    "timestamp": datetime.now(tz), "name": p_name, "category": p_cat,
                    "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                    "bed_no": "", "status": "WAITING", "date": today_date_str
                })
                st.session_state.pop('last_fetch') # Force refresh on next load
                st.rerun()

# --- 5. SIDEBAR (ADMIN & BOOKINGS) ---
show_dashboard = False 
with st.sidebar:
    st.header("📅 Future Booking")
    with st.expander("📝 ADD BOOKING"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Name"); f_uhid = st.text_input("UHID"); f_dr = st.text_input("Dr.")
            f_date = st.date_input("Date"); f_pref = st.selectbox("Bed", ["DELUXE", "PRIVATE", "SEMI"])
            if st.form_submit_button("Save"):
                db.collection("future_bookings").add({
                    "name": f_name, "uhid": f_uhid, "dr": f_dr, 
                    "book_date": f_date.strftime('%Y-%m-%d'), "preference": f_pref
                })
                st.session_state.pop('last_fetch')
                st.rerun()

    if book_list:
        remove_sel = st.selectbox("Delete Booking", ["Select"] + [b['name'] for b in book_list])
        if st.button("Confirm Delete"):
            b_id = next(b['ID'] for b in book_list if b['name'] == remove_sel)
            db.collection("future_bookings").document(b_id).delete()
            st.session_state.pop('last_fetch')
            st.rerun()

    st.divider(); st.header("🛡️ Admin Panel")
    if st.text_input("Password", type="password") == "GeimsAdmin99":
        show_dashboard = True 
        if st.button("CLEAR REQUEST LIST"):
            for r in db.collection("bed_requests").stream(): r.reference.delete()
            st.session_state.pop('last_fetch')
            st.rerun()

# --- 6. VISUAL DASHBOARD ---
if show_dashboard:
    status_colors = {"VACANT": "#FFFFFF", "ALLOTTED": "#000000", "MAINTENANCE": "#E0E0E0"}
    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing); cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
            txt = "white" if data.get('status') == "ALLOTTED" else "black"
            with cols[i % 5]:
                st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:80px; font-size:11px;"><b>{bed}</b><br>{data.get("status", "VACANT")}<br><i>{data.get("patient", "")}</i></div>', unsafe_allow_html=True)
else:
    st.info("🔒 Enter Admin Password in sidebar.")
