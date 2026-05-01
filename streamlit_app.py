import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime
import pytz

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- QUANTUM FLUID + ULTRA-GLASS 3D INTERFACE ---
st.markdown("""
<style>
    /* 1. THE MOVING BACKGROUND: SHARP & VIVID */
    [data-testid="stAppViewContainer"] {
        background-image: url("https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTNqazRwZDFlMjcwaTl6OHlvY21ucGd3YWoxaWYycjVsaG1jeGhmbyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/U4ExkAvRpVQGB0NMe0/giphy.gif") !important;
        background-size: cover !important;
        background-position: center !important;
        background-attachment: fixed !important;
    }

    /* 2. BALANCED BRIGHTNESS OVERLAY */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        /* Dark blue/black tint to allow high brightness but maintain text contrast */
        background: rgba(5, 10, 20, 0.55); 
        z-index: 0;
        pointer-events: none;
    }

    /* 3. PREMIUM 3D TACTILE GLASS BUTTONS */
    div.stButton > button {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 14px !important;
        padding: 0.7rem 1.8rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        /* Professional 3D Shadow with depth */
        box-shadow: 0 5px 0px rgba(0,0,0,0.5), 0 8px 20px rgba(0, 229, 255, 0.2) !important;
        transition: all 0.1s cubic-bezier(0.4, 0, 0.2, 1) !important;
        backdrop-filter: blur(12px);
    }

    div.stButton > button:hover {
        background: rgba(255, 255, 255, 0.22) !important;
        transform: translateY(-2px);
        box-shadow: 0 7px 0px rgba(0,0,0,0.5), 0 15px 25px rgba(0, 229, 255, 0.4) !important;
    }

    /* 3D "Mechanical Click" */
    div.stButton > button:active {
        transform: translateY(5px) !important;
        box-shadow: 0 0px 0px transparent !important;
        background: rgba(0, 229, 255, 0.2) !important;
        color: #00e5ff !important;
    }

    /* 4. ULTRA-TRANSPARENT CRYSTAL PANELS (Glassmorphism) */
    [data-testid="stMetric"], .stForm, .stExpander {
        background: rgba(255, 255, 255, 0.06) !important; 
        backdrop-filter: blur(28px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 22px !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6) !important;
        z-index: 1;
        margin-bottom: 25px !important;
    }

    /* 5. TYPOGRAPHY: SHARP & READABLE */
    h1 {
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 0 4px 15px rgba(0,0,0,0.7);
        text-align: center;
        letter-spacing: 2px;
    }

    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        text-shadow: 0 0 20px rgba(0, 229, 255, 0.6);
        font-weight: 800 !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: rgba(255, 255, 255, 0.85) !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        font-size: 0.85rem !important;
    }

    /* Sidebar Glass UI (Matching the main dashboard) */
    [data-testid="stSidebar"] {
        background-color: rgba(0, 5, 15, 0.85) !important;
        backdrop-filter: blur(24px);
        border-right: 1px solid rgba(255, 255, 255, 0.15);
    }

    /* Professional Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.25); border-radius: 10px; }
    ::-webkit-scrollbar-track { background: transparent; }
</style>
""", unsafe_allow_html=True)

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
    if 'cached_live_data' not in st.session_state or 'cached_req_list' not in st.session_state:
        status_doc = db.collection("settings").document("dashboard_status").get()
        st.session_state.is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"
        docs = db.collection("beds").stream()
        st.session_state.cached_live_data = {doc.id: doc.to_dict() for doc in docs}
        
        reqs_stream = db.collection("bed_requests").limit(100).stream()
        raw_reqs = [r.to_dict() | {'ID': r.id} for r in reqs_stream]
        st.session_state.cached_req_list = sorted(raw_reqs, key=lambda x: (x.get('position', 999), x.get('timestamp', datetime.min)))
        
        book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).stream()
        st.session_state.cached_book_list = [b.to_dict() | {'ID': b.id} for b in book_stream]

    live_data = st.session_state.cached_live_data
    req_list = st.session_state.cached_req_list
    book_list = st.session_state.cached_book_list
else:
    st.error("Database Connection Failed."); st.stop()

# --- 4. HEADER ---
tz = pytz.timezone('Asia/Kolkata')
today_date_str = datetime.now(tz).strftime('%d/%m/%Y')
today_iso = datetime.now(tz).strftime('%Y-%m-%d')

st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date_str}</b></p>", unsafe_allow_html=True)

if st.button("🔄 Refresh Dashboard Data"):
    for key in ['cached_live_data', 'is_live', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='background-color: #FFEBEE; border: 2px solid #FF5252; padding: 15px; border-radius: 5px; margin-bottom: 5px;'><b>🚨 TODAY'S BOOKING: {a.get('name', 'N/A')}</b></div>", unsafe_allow_html=True)
        if st.button(f"✅ Admit: {a.get('name')}", key=f"ack_{a['ID']}"):
            db.collection("bed_requests").add({
                "timestamp": datetime.now(tz), "name": a.get('name'), "category": a.get('category', 'OTHER'),
                "dr_name": a.get('dr'), "shift_from": "BOOKING", "shift_to": a.get('preference', 'PVT'), 
                "remark": f"Reserved: {a.get('pref_bed','-')}", "bed_no": "", "status": "WAITING", 
                "date": today_date_str, "position": 999
            })
            db.collection("future_bookings").document(a['ID']).delete()
            for k in ['cached_req_list', 'cached_book_list']: 
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# --- 6. MANAGE PATIENT REQUESTS ---
with st.expander("📋 MANAGE PATIENT REQUESTS", expanded=True):
    pending = sum(1 for r in req_list if r.get('status') == "WAITING" and not r.get('bed_no'))
    allotted = sum(1 for r in req_list if r.get('status') == "DONE")
    st.columns(2)[0].metric("Pending", pending)
    st.columns(2)[1].metric("Done", allotted)
    st.divider()

    with st.form("new_req", clear_on_submit=True):
        st.subheader("New Shifting Request Entry")
        c1, c2 = st.columns(2)
        p_name = c1.text_input("PATIENT NAME")
        p_cat = c1.selectbox("CATEGORY", ["SELF PAY", "ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "ICAR", "AYUSHMAN", "OTHER"])
        dr_name = c1.text_input("ADMITTED UNDER DOCTOR")
        p_fr = c2.selectbox("SHIFT FROM", ["CCU", "EMERGENCY", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
        p_to = c2.selectbox("SHIFTING TO", ["DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        rem = c2.text_input("REMARK")
        if st.form_submit_button("Submit Request"):
            if p_name:
                db.collection("bed_requests").add({
                    "timestamp": datetime.now(tz), "name": p_name, "category": p_cat,
                    "dr_name": dr_name, "shift_from": p_fr, "shift_to": p_to, 
                    "remark": rem, "bed_no": "", "status": "WAITING", "date": today_date_str, "position": 999
                })
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

    if req_list:
        st.divider()
        sq = st.text_input("🔍 Search Patient Name", "").lower()
        h_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
        headers = ["S.N", "NAME", "CAT", "DR", "FROM", "TO", "REMARK", "BED", "STATUS", "ACTION"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        for idx, r in enumerate(req_list):
            if sq and sq not in r.get('name', '').lower(): continue
            
            current_status = r.get('status', 'WAITING')
            b_no = r.get('bed_no', '')
            if b_no and current_status == "WAITING": current_status = "DONE"
            
            r_cols = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 1, 1, 1.5])
            r_cols[0].write(idx + 1); r_cols[1].write(r.get('name', '-')); r_cols[2].write(r.get('category', '-'))
            r_cols[3].write(r.get('dr_name', '-')); r_cols[4].write(r.get('shift_from', '-')); r_cols[5].write(r.get('shift_to', '-'))
            r_cols[6].write(r.get('remark', '-')); r_cols[7].write(b_no if b_no else "-")
            color_map = {"DONE": "green", "CANCELLED": "red", "GEN-WARD ALLOTTED": "blue", "HOLD": "purple"}
            color = color_map.get(current_status, "orange")
            r_cols[8].markdown(f"<span style='color:{color}; font-weight:bold;'>{current_status}</span>", unsafe_allow_html=True)
            if current_status == "DONE":
                slip = f"""====================================\n      G.E.I.M.S (Bed Management)\n      BED ALLOTMENT SLIP\n====================================\nDATE: {today_date_str}\nPATIENT: {r['name']}\n------------------------------------\nBED:  {b_no}\n===================================="""
                r_cols[9].download_button("🖨️ Slip", data=slip, file_name=f"Slip_{r['name']}.txt", key=f"rec_{r['ID']}")

# --- NEW: PDF CONSENT FORM PANEL ---
st.subheader("📝 ADMISSION & SHIFTING CONSENT FORMS (PDF)")

# Function to safely read PDF files from your GitHub folder
def get_pdf_data(file_name):
    try:
        with open(file_name, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns(5)

# 1. SELF PAY
pdf_self = get_pdf_data("consent_self_pay.pdf")
with c_col1:
    if pdf_self:
        st.download_button("💳 1 - SELF PAY", pdf_self, file_name="Consent_SelfPay.pdf", mime="application/pdf")
    else:
        st.error("Self Pay PDF Missing")

# 2. CGHS CASH
pdf_cghs_cash = get_pdf_data("consent_cghs_cash.pdf")
with c_col2:
    if pdf_cghs_cash:
        st.download_button("💰 2 - CGHS CASH", pdf_cghs_cash, file_name="Consent_CGHS_Cash.pdf", mime="application/pdf")
    else:
        st.error("CGHS Cash PDF Missing")

# 3. ECHS
pdf_echs = get_pdf_data("consent_echs.pdf")
with c_col3:
    if pdf_echs:
        st.download_button("🎖️ 3 - ECHS", pdf_echs, file_name="Consent_ECHS.pdf", mime="application/pdf")
    else:
        st.error("ECHS PDF Missing")

# 4. CGHS CREDIT & PSU
pdf_cghs_credit = get_pdf_data("consent_cghs_credit.pdf")
with c_col4:
    if pdf_cghs_credit:
        st.download_button("🏥 4 - CGHS CREDIT/PSU", pdf_cghs_credit, file_name="Consent_CGHS_Credit.pdf", mime="application/pdf")
    else:
        st.error("Credit PDF Missing")

# 5. TPA
pdf_tpa = get_pdf_data("consent_tpa.pdf")
with c_col5:
    if pdf_tpa:
        st.download_button("🏢 5 - TPA", pdf_tpa, file_name="Consent_TPA.pdf", mime="application/pdf")
    else:
        st.error("TPA PDF Missing")

# --- 7. SIDEBAR ---
show_dashboard = False 
with st.sidebar:
    st.header("📅 Future Booking Control")
    with st.expander("📝 ADD FUTURE BOOKING"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Patient Name"); f_uhid = st.text_input("UHID No."); f_dr = st.text_input("Doctor Name")
            f_date = st.date_input("Booking Date"); f_room = st.text_input("Pre-decided Bed ID"); f_cat = st.selectbox("Category", ["SELF PAY", "OTHER"]); f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            if st.form_submit_button("Save"):
                db.collection("future_bookings").add({"name": f_name, "uhid": f_uhid, "dr": f_dr, "book_date": f_date.strftime('%Y-%m-%d'), "category": f_cat, "preference": f_pref, "pref_bed": f_room})
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    st.divider(); st.header("🛡️ Admin Panel")
    if st.text_input("Admin Password", type="password") == "GeimsAdmin99":
        show_dashboard = True 
        
        # 📋 REPORTS
        st.subheader("📋 Reports")
        if st.button("Download Handover Summary"):
            done = [r for r in req_list if r.get('bed_no')]
            rep = f"GEIMS SHIFT REPORT - {today_date_str}\n\n"
            for r in done: rep += f"- {r['name']} -> Bed: {r['bed_no']}\n"
            st.download_button("📥 Get Report", data=rep, file_name=f"Handover_{today_date_str}.txt")

        # ↕️ MANUAL LIST SWITCHER
        st.divider(); st.subheader("↕️ Switch Positions")
        if len(req_list) >= 2:
            p1_name = st.selectbox("Move Patient", [r['name'] for r in req_list], key="reorder_p1")
            p2_name = st.selectbox("With Patient", [r['name'] for r in req_list], key="reorder_p2")
            if st.button("Execute Switch"):
                p1 = next(r for r in req_list if r['name'] == p1_name); p2 = next(r for r in req_list if r['name'] == p2_name)
                db.collection("bed_requests").document(p1['ID']).update({"position": p2.get('position', 999)})
                db.collection("bed_requests").document(p2['ID']).update({"position": p1.get('position', 999)})
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

        # 🛠️ PATIENT MODIFICATION HUB
        st.divider(); st.subheader("🛠️ Patient Modification Hub")
        if req_list:
            p_map = {f"{r['name']} ({r.get('bed_no', 'No Bed')})": r['ID'] for r in req_list}
            selected_label = st.selectbox("Select Patient Record", list(p_map.keys()))
            target_id = p_map[selected_label]; target_data = next(r for r in req_list if r['ID'] == target_id)
            new_status = st.selectbox("Change Status", ["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"], index=["WAITING", "DONE", "HOLD", "CANCELLED", "GEN-WARD ALLOTTED"].index(target_data.get('status', 'WAITING')))
            new_bed = st.text_input("Change Bed ID", value=target_data.get('bed_no', ''))
            if st.button("🔥 SYNC & UPDATE"):
                old_bed = target_data.get('bed_no')
                if old_bed and old_bed in all_bed_ids: db.collection("beds").document(old_bed).set({"status": "VACANT", "patient": ""})
                if new_bed and new_bed in all_bed_ids and new_status == "DONE": db.collection("beds").document(new_bed).set({"status": "ALLOTTED", "patient": target_data['name']})
                db.collection("bed_requests").document(target_id).update({"status": new_status, "bed_no": new_bed})
                for k in ['cached_req_list', 'cached_live_data']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

        # 🔑 ALLOTMENT TOOLS
        st.divider(); st.subheader("🔑 Allotment Tools")
        wait = [r for r in req_list if not r.get('bed_no') and r.get('status') == "WAITING"]
        if wait:
            p_sel = st.selectbox("Assign Patient", [r['name'] for r in wait])
            b_val = st.text_input("Bed ID", key="allot_b")
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in wait if r['name'] == p_sel)
                db.collection("bed_requests").document(r_id).update({"bed_no": b_val, "status": "DONE"})
                if b_val in all_bed_ids: db.collection("beds").document(b_val).set({"status": "ALLOTTED", "patient": p_sel})
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

        # 📝 ENTRY MODIFICATION (Remark/Cancel)
        st.divider(); st.subheader("📝 Entry Modification")
        if req_list:
            target = st.selectbox("Select Patient to Edit", [r['name'] for r in req_list], key="sb_mod")
            action = st.radio("Action", ["Edit Remark", "Mark as CANCELLED", "Delete Entry"], horizontal=True)
            new_val = st.text_input("New Remark")
            if st.button("Confirm Modification"):
                r_id = next(r['ID'] for r in req_list if r['name'] == target)
                if action == "Delete Entry": db.collection("bed_requests").document(r_id).delete()
                elif action == "Mark as CANCELLED": db.collection("bed_requests").document(r_id).update({"status": "CANCELLED", "bed_no": ""})
                else: db.collection("bed_requests").document(r_id).update({"remark": new_val})
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

        # ⚙️ MANUAL BED UPDATE
        st.divider(); st.subheader("⚙️ Manual Bed Update")
        m_bed = st.selectbox("Select Bed", all_bed_ids); m_stat = st.selectbox("Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE", "RESTRICTED"]); m_name = st.text_input("Name Override")
        if st.button("Apply Bed Update"):
            db.collection("beds").document(m_bed).set({"status": m_stat, "patient": m_name})
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
            st.rerun()

        # ⚠️ DATA RESET
        st.divider(); st.error("⚠️ DATA RESET")
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
            st.rerun()
        if st.button("CLEAR REQUEST LIST"):
            for r in db.collection("bed_requests").stream(): r.reference.delete()
            if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
            st.rerun()

# --- 8. VISUAL DASHBOARD ---
if show_dashboard:
    status_colors = {"VACANT": "#FFFFFF", "BOOKED": "#90EE90", "ALLOTTED": "#000000", "DISCHARGE": "#ADD8E6", "MAINTENANCE": "#E0E0E0", "RESTRICTED": "#FF0000"}
    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing); cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": ""})
            bg = status_colors.get(data.get('status', 'VACANT'), "#FFFFFF")
            txt = "white" if data.get('status') in ["ALLOTTED", "RESTRICTED"] else "black"
            with cols[i % 5]:
                st.markdown(f'<div style="background-color:{bg}; color:{txt}; padding:5px; border:1px solid #ccc; border-radius:5px; text-align:center; height:85px; font-size:11px;"><b>{bed}</b><br><span style="font-size:10px; font-weight:bold;">{data.get("status", "VACANT")}</span><br><i style="font-size:10px;">{data.get("patient", "")}</i></div>', unsafe_allow_html=True)
else:
    st.info("🔒 Enter Admin Password in sidebar to view Bed Status.")
