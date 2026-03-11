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

# --- 3. FAILSAFE DATA FETCH ---
if db:
    # Check if memory is empty; if so, fetch once
    if 'cached_live_data' not in st.session_state or 'cached_req_list' not in st.session_state:
        try:
            status_doc = db.collection("settings").document("dashboard_status").get()
            st.session_state.is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"

            docs = db.collection("beds").stream()
            st.session_state.cached_live_data = {doc.id: doc.to_dict() for doc in docs}

            reqs_stream = db.collection("bed_requests").order_by("timestamp", direction=firestore.Query.ASCENDING).limit(100).stream()
            st.session_state.cached_req_list = [r.to_dict() | {'ID': r.id} for r in reqs_stream]
            
            book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).stream()
            st.session_state.cached_book_list = [b.to_dict() | {'ID': b.id} for b in book_stream]
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()

    # Safely assign local variables
    is_live = st.session_state.get('is_live', "LIVE")
    live_data = st.session_state.get('cached_live_data', {})
    req_list = st.session_state.get('cached_req_list', [])
    book_list = st.session_state.get('cached_book_list', [])
else:
    st.error("Database Connection Failed."); st.stop()

# --- 4. HEADER & MANUAL REFRESH ---
tz = pytz.timezone('Asia/Kolkata')
today_date_str = datetime.now(tz).strftime('%d/%m/%Y')
today_iso = datetime.now(tz).strftime('%Y-%m-%d')

st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date_str}</b></p>", unsafe_allow_html=True)

# Button to manually clear memory and pull new data
if st.button("🔄 Refresh Dashboard Data"):
    for key in ['cached_live_data', 'is_live', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    st.markdown(f"""
        <div style="background-color: #FFEBEE; border: 2px solid #FF5252; padding: 10px; border-radius: 5px; margin-bottom: 10px; animation: blinker 1.5s linear infinite;">
            <span style="color: #D32F2F; font-weight: bold;">🚨 TODAY'S BOOKING ALERT:</span> 
            <b>{a['name']}</b> (UHID: {a.get('uhid','-')}) - Dr. {a.get('dr','-')}
        </div>
        <style> @keyframes blinker {{ 50% {{ opacity: 0.4; }} }} </style>
    """, unsafe_allow_html=True)

# --- 6. MANAGE REQUESTS ---
with st.expander("📋 MANAGE PATIENT REQUESTS", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('bed_no') != "")
    
    s1, s2 = st.columns(2)
    s1.metric("Pending", pending); s2.metric("Done", allotted)
    st.divider()

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
                # Clear cache so it fetches new list
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

    if req_list:
        st.divider()
        sq = st.text_input("🔍 Search Patient Name", "").lower()
        st.subheader("Shifting Request Status List")
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["S.N", "NAME", "CAT", "DR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        
        for idx, r in enumerate(req_list):
            if sq and sq not in r.get('name', '').lower(): continue
            b_no = r.get('bed_no', ''); status = r.get('status', 'WAITING')
            if b_no: status = "DONE"
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-')); r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-')); r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
            color = "green" if status == "DONE" else ("red" if status == "CANCELLED" else "orange")
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{status}</span>", unsafe_allow_html=True)
            if status == "DONE":
                slip = f"====================================\n      G.E.I.M.S (Bed Management)\n      BED ALLOTMENT SLIP\n====================================\nDATE: {today_date_str}\nPATIENT: {r['name']}\n------------------------------------\nBED:  {b_no}\n===================================="
                r_cols[9].download_button("🖨️ Slip", data=slip, file_name=f"Slip_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- 7. SIDEBAR ---
show_dashboard = False 
with st.sidebar:
    st.header("📅 Future Booking")
    with st.expander("📝 ADD FUTURE BOOKING"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Patient Name"); f_uhid = st.text_input("UHID"); f_dr = st.text_input("Doctor")
            f_date = st.date_input("Date"); f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            if st.form_submit_button("Save"):
                db.collection("future_bookings").add({
                    "name": f_name, "uhid": f_uhid, "dr": f_dr, "book_date": f_date.strftime('%Y-%m-%d'), "preference": f_pref
                })
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    if book_list:
        st.divider(); st.subheader("Manage Bookings")
        remove_sel = st.selectbox("Delete Booking", ["Select"] + [b['name'] for b in book_list])
        if st.button("Confirm Delete"):
            if remove_sel != "Select":
                b_id = next(b['ID'] for b in book_list if b['name'] == remove_sel)
                db.collection("future_bookings").document(b_id).delete()
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    st.divider(); st.header("🛡️ Admin Panel")
    if st.text_input("Admin Password", type="password") == "GeimsAdmin99":
        show_dashboard = True 
        st.subheader("🔑 Allotment Tools")
        wait = [r for r in req_list if not r.get('bed_no') and r.get('status') == "WAITING"]
        if wait:
            p_sel = st.selectbox("Assign Patient", [r['name'] for r in wait])
            b_val = st.text_input("Enter Bed ID")
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in wait if r['name'] == p_sel)
                db.collection("bed_requests").document(r_id).update({"bed_no": b_val, "status": "DONE"})
                if b_val in all_bed_ids: db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
                st.rerun()

# --- 8. VISUAL DASHBOARD ---
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
                st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:85px; font-size:11px;"><b>{bed}</b><br><span style="font-size:10px; font-weight:bold;">{data.get("status", "VACANT")}</span><br><i style="font-size:10px;">{data.get("patient", "")}</i></div>', unsafe_allow_html=True)
else:
    st.info("🔒 Enter Admin Password in sidebar to view Bed Status.")
