import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime, timedelta
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

    /* Sidebar Glass UI */
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

# --- 3. FAILSAFE DATA FETCH (IST Timezone Standardized) ---
ist_tz = pytz.timezone('Asia/Kolkata')
today_ist = datetime.now(ist_tz)
today_date_str = today_ist.strftime('%d/%m/%Y')

if db:
    if 'cached_live_data' not in st.session_state or 'cached_req_list' not in st.session_state:
        status_doc = db.collection("settings").document("dashboard_status").get()
        st.session_state.is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"
        docs = db.collection("beds").stream()
        st.session_state.cached_live_data = {doc.id: doc.to_dict() for doc in docs}
        
        reqs_stream = db.collection("bed_requests").limit(100).stream()
        raw_reqs = []
        for r in reqs_stream:
            data = r.to_dict()
            ts = data.get('timestamp')
            if ts:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                data['timestamp'] = ts
            raw_reqs.append(data | {'ID': r.id})
            
        st.session_state.cached_req_list = sorted(raw_reqs, key=lambda x: (x.get('position', 999), x.get('timestamp', today_ist)))
        
        book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).stream()
        st.session_state.cached_book_list = [b.to_dict() | {'ID': b.id} for b in book_stream]

    live_data = st.session_state.cached_live_data
    req_list = st.session_state.cached_req_list
    book_list = st.session_state.cached_book_list
else:
    st.error("Database Connection Failed."); st.stop()

# --- 4. HEADER ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date_str}</b></p>", unsafe_allow_html=True)

if st.button("🔄 Refresh Dashboard Data"):
    for key in ['cached_live_data', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. ALERTS ---
today_iso = today_ist.strftime('%Y-%m-%d')
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='background-color: #FFEBEE; border: 2px solid #FF5252; padding: 15px; border-radius: 5px; margin-bottom: 5px;'><b>🚨 TODAY'S BOOKING: {a.get('name', 'N/A')}</b></div>", unsafe_allow_html=True)
        if st.button(f"✅ Admit: {a.get('name')}", key=f"ack_{a['ID']}"):
            db.collection("bed_requests").add({
                "timestamp": datetime.now(ist_tz),
                "name": a.get('name'), "category": a.get('category', 'OTHER'),
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
                p_name_clean = p_name.strip().lower()
                p_dr_clean = dr_name.strip().lower()
                is_duplicate = False
                
                for r in req_list:
                    if (r.get('name', '').strip().lower() == p_name_clean and 
                        r.get('category') == p_cat and 
                        r.get('dr_name', '').strip().lower() == p_dr_clean and 
                        r.get('shift_from') == p_fr and 
                        r.get('shift_to') == p_to and 
                        r.get('status') == "WAITING"):
                        is_duplicate = True
                        break
                        
                if is_duplicate:
                    st.warning("⚠️ Duplicate Entry: An identical shifting request already exists in the list.")
                else:
                    db.collection("bed_requests").add({
                        "timestamp": datetime.now(ist_tz), 
                        "name": p_name, "category": p_cat,
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
                
            ts = r.get('timestamp')
            if ts:
                if ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                ts_ist = ts.astimezone(ist_tz)
                ts_str = ts_ist.strftime('%d/%m/%Y %I:%M:%S %p')
            else:
                ts_str = "-"
            st.markdown(f"<div style='font-size: 11px; color: rgba(255,255,255,0.7); margin-left: 35px; margin-top: -12px; margin-bottom: 12px;'>🕒 Entry Timestamp (IST): <b>{ts_str}</b></div>", unsafe_allow_html=True)

# --- PDF CONSENT FORM PANEL ---
st.subheader("📝 ADMISSION & SHIFTING CONSENT FORMS (PDF)")

def get_pdf_data(file_name):
    try:
        with open(file_name, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns(5)
with c_col1:
    st.download_button("💳 1 - SELF PAY", get_pdf_data("consent_self_pay.pdf") or b"", file_name="Consent_SelfPay.pdf", mime="application/pdf")
with c_col2:
    st.download_button("💰 2 - CGHS CASH", get_pdf_data("consent_cghs_cash.pdf") or b"", file_name="Consent_CGHS_Cash.pdf", mime="application/pdf")
with c_col3:
    st.download_button("🎖️ 3 - ECHS", get_pdf_data("consent_echs.pdf") or b"", file_name="Consent_ECHS.pdf", mime="application/pdf")
with c_col4:
    st.download_button("🏥 4 - CGHS CREDIT/PSU", get_pdf_data("consent_cghs_credit.pdf") or b"", file_name="Consent_CGHS_Credit.pdf", mime="application/pdf")
with c_col5:
    st.download_button("🏢 5 - TPA", get_pdf_data("consent_tpa.pdf") or b"", file_name="Consent_TPA.pdf", mime="application/pdf")

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
        
        st.subheader("📋 Reports")
        
        report_data = []
        for idx, r in enumerate(req_list):
            ts = r.get('timestamp')
            if ts:
                if ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                ts_ist = ts.astimezone(ist_tz)
                ts_str = ts_ist.strftime('%d/%m/%Y %I:%M:%S %p')
            else:
                ts_str = "-"
                
            report_data.append({
                "S.N": idx + 1,
                "NAME": r.get('name', '-'),
                "Date & time stamp": ts_str,
                "CAT": r.get('category', '-'),
                "DR": r.get('dr_name', '-'),
                "FROM": r.get('shift_from', '-'),
                "TO": r.get('shift_to', '-'),
                "REMARK": r.get('remark', '-'),
                "BED": r.get('bed_no') if r.get('bed_no') else "-",
                "STATUS": r.get('status', 'WAITING')
            })
            
        df_report = pd.DataFrame(report_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_report.to_excel(writer, sheet_name="Handover Report", index=False)
            
        st.download_button(
            label="📥 Download Handover Summary",
            data=buffer.getvalue(),
            file_name=f"Handover_{today_date_str.replace('/', '-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.divider(); st.subheader("↕️ Manual List Reordering")
        if req_list:
            reorder_p = st.selectbox("Select Patient to Move", [r['name'] for r in req_list], key="reorder_sel")
            new_pos = st.number_input("New Position Number (1, 2, 3...)", min_value=1, value=10, step=1)
            if st.button("Apply Position Change"):
                target_r = next(r for r in req_list if r['name'] == reorder_p)
                
                sorted_list = sorted(req_list, key=lambda x: x.get('position', 999))
                sorted_list = [i for i in sorted_list if i['ID'] != target_r['ID']]
                sorted_list.insert(int(new_pos) - 1, target_r)
                
                for idx, r in enumerate(sorted_list):
                    db.collection("bed_requests").document(r['ID']).update({"position": idx + 1})
                    
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.success(f"Moved {reorder_p} to Position {new_pos}"); st.rerun()

        st.divider(); st.subheader("🔄 Bed & Status Alteration")
        if req_list:
            alt_p = st.selectbox("Select Patient to Alter", [r['name'] for r in req_list], key="alt_p_sel")
            c1, c2 = st.columns(2)
            new_b = c1.text_input("New Bed ID")
            new_s = c2.selectbox("Alter Status", ["DONE", "WAITING", "CANCELLED", "HOLD", "GEN-WARD ALLOTTED"])
            if st.button("Apply Alteration"):
                p_data = next(r for r in req_list if r['name'] == alt_p)
                old_bed = p_data.get('bed_no')
                
                db.collection("bed_requests").document(p_data['ID']).update({"status": new_s, "bed_no": new_b})
                if old_bed in all_bed_ids:
                    db.collection("beds").document(old_bed).set({"status": "VACANT", "patient": ""})
                if new_b and new_b in all_bed_ids:
                    db.collection("beds").document(new_b).set({"status": "ALLOTTED", "patient": alt_p})
                    
                st.success(f"Updated {alt_p} successfully.")
                for k in ['cached_req_list', 'cached_live_data']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

        # 📝 ENTRY MODIFICATION (RE-ADDED)
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

        st.divider(); st.subheader("⚙️ Manual Bed Update")
        m_bed = st.selectbox("Select Bed ID", all_bed_ids); m_stat = st.selectbox("Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE", "RESTRICTED"]); m_name = st.text_input("Name Override")
        if st.button("Apply Bed Update"):
            db.collection("beds").document(m_bed).set({"status": m_stat, "patient": m_name})
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
            st.rerun()

        st.divider(); st.error("⚠️ DATA RESET")
        if st.button("RESET ALL BEDS"):
            for b in all_bed_ids: db.collection("beds").document(b).set({"status": "VACANT", "patient": ""})
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
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
