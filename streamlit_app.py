import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime, timedelta
import pytz
import io
import re
import streamlit.components.v1 as components
import requests
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIG ---
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- 0. AUTO-REFRESH & CACHE INVALIDATION (30 SECONDS) ---
refresh_count = st_autorefresh(interval=30000, key="bed_dashboard_autorefresh")

if "last_refresh_count" not in st.session_state or st.session_state.last_refresh_count != refresh_count:
    st.session_state.last_refresh_count = refresh_count
    for key in ['cached_live_data', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state:
            del st.session_state[key]

# --- SIMPLE MATTE PRIORITY CONFIG (INTERNAL ONLY - NO GLOW) ---
PRIORITY_CONFIG = {
    "VIP":       {"weight": 1, "color": "#F59E0B", "bg": "#272015", "border": "#B45309"},
    "HWC":       {"weight": 2, "color": "#38BDF8", "bg": "#112233", "border": "#0284C7"},
    "GEU":       {"weight": 3, "color": "#10B981", "bg": "#0F2922", "border": "#059669"},
    "IMPORTANT": {"weight": 4, "color": "#F43F5E", "bg": "#2A141B", "border": "#E11D48"},
    "STANDARD":  {"weight": 5, "color": "#94A3B8", "bg": "#1E293B", "border": "#475569"}
}

# --- NTFY MOBILE PUSH NOTIFICATION HELPER ---
NTFY_TOPIC = "geims-bed-tracker-alerts-99"

def send_ntfy_notification(title, message, priority="urgent", tags="hospital,warning"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags
            },
            timeout=5
        )
    except Exception:
        pass

# --- ADVANCED PRINTABLE HTML RECEIPT GENERATOR (IMAGE USED ONLY HERE, NO PRIORITY) ---
def generate_advanced_receipt_html(req_data, date_str, generated_time_str):
    patient_name = req_data.get('name', '-')
    uhid = req_data.get('uhid') or 'N/A'
    category = req_data.get('category', '-')
    dr_name = req_data.get('dr_name', '-')
    shift_from = req_data.get('shift_from', '-')
    shift_to = req_data.get('shift_to', '-')
    bed_no = req_data.get('bed_no', '-')
    remark = req_data.get('remark') or 'None'
    slip_id = str(req_data.get('ID', '0000'))[:8].upper()
    bg_url = "https://mdmsenquiry.com/wp-content/uploads/2024/07/GEIMS-Dehradun-1.png"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Bed Allotment Receipt - {patient_name}</title>
    <style>
        @page {{ size: A5 landscape; margin: 10mm; }}
        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #e2e8f0;
            color: #0f172a;
            margin: 0;
            padding: 25px;
        }}
        .receipt-card {{
            position: relative;
            max-width: 740px;
            margin: 0 auto;
            background-color: #ffffff;
            border: 2px solid #0f172a;
            border-radius: 8px;
            overflow: hidden;
        }}
        /* GEIMS Image Background Watermark exclusively inside Receipt */
        .receipt-bg {{
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-image: url('{bg_url}');
            background-size: cover;
            background-position: center;
            opacity: 0.12;
            z-index: 0;
            pointer-events: none;
        }}
        .receipt-inner {{
            position: relative;
            z-index: 1;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(15, 23, 42, 0.96);
            color: #ffffff;
            padding: 16px 24px;
            border-bottom: 3px solid #2563eb;
        }}
        .header-left h1 {{
            margin: 0;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .header-left p {{
            margin: 4px 0 0 0;
            font-size: 12px;
            color: #cbd5e1;
        }}
        .header-logo {{
            width: 95px;
            height: 56px;
            object-fit: cover;
            border-radius: 6px;
            border: 1.5px solid #94a3b8;
        }}
        .sub-bar {{
            display: flex;
            justify-content: space-between;
            background: rgba(248, 250, 252, 0.92);
            padding: 9px 24px;
            border-bottom: 1px solid #cbd5e1;
            font-size: 12px;
            font-weight: 700;
            color: #1e293b;
        }}
        .content {{
            padding: 20px 24px;
        }}
        .bed-highlight {{
            background: rgba(239, 246, 255, 0.92);
            border: 1.5px solid #60a5fa;
            border-radius: 6px;
            padding: 12px 18px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .bed-highlight .label {{
            font-size: 12px;
            font-weight: 800;
            color: #1e40af;
            text-transform: uppercase;
        }}
        .bed-highlight .value {{
            font-size: 21px;
            font-weight: 900;
            color: #1e3a8a;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            background: rgba(255, 255, 255, 0.88);
        }}
        td {{
            padding: 9px 12px;
            border: 1px solid #94a3b8;
        }}
        td.field {{
            background: rgba(241, 245, 249, 0.92);
            font-weight: 700;
            color: #1e293b;
            width: 22%;
            text-transform: uppercase;
            font-size: 11.5px;
        }}
        td.val {{
            font-weight: 600;
            color: #0f172a;
            width: 28%;
        }}
        .signatures {{
            display: flex;
            justify-content: space-between;
            margin-top: 34px;
            padding-top: 10px;
            font-size: 12px;
            color: #1e293b;
        }}
        .sig-box {{
            border-top: 1.5px dashed #334155;
            width: 210px;
            text-align: center;
            padding-top: 6px;
            font-weight: 700;
        }}
        .validity-footer {{
            background: #fef2f2;
            border-top: 2px solid #dc2626;
            color: #991b1b;
            text-align: center;
            padding: 10px 16px;
            font-size: 12.5px;
            font-weight: 800;
            letter-spacing: 0.4px;
        }}
        .print-btn-wrap {{
            text-align: center;
            margin-bottom: 15px;
        }}
        .print-btn {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 22px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
            font-size: 13px;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .print-btn-wrap {{ display: none; }}
            .receipt-card {{ border: 2px solid #000; }}
        }}
    </style>
</head>
<body>
    <div class="print-btn-wrap">
        <button class="print-btn" onclick="window.print()">🖨️ Print Official Bed Allotment Receipt</button>
    </div>
    <div class="receipt-card">
        <div class="receipt-bg"></div>
        <div class="receipt-inner">
            <div class="header">
                <div class="header-left">
                    <h1>Graphic Era Institute of Medical Sciences</h1>
                    <p>IPD Bed Management & Official Allotment Receipt • Dehradun, Uttarakhand</p>
                </div>
                <img class="header-logo" src="{bg_url}" alt="GEIMS">
            </div>
            <div class="sub-bar">
                <span>RECEIPT NO: GEIMS-{slip_id}</span>
                <span>DATE OF ISSUE: {date_str} ({generated_time_str})</span>
            </div>
            <div class="content">
                <div class="bed-highlight">
                    <span class="label">Allotted Ward / Bed Number</span>
                    <span class="value">{bed_no}</span>
                </div>
                <table>
                    <tr>
                        <td class="field">Patient Name</td>
                        <td class="val">{patient_name}</td>
                        <td class="field">UHID Number</td>
                        <td class="val">{uhid}</td>
                    </tr>
                    <tr>
                        <td class="field">Admitting Doctor</td>
                        <td class="val">{dr_name}</td>
                        <td class="field">Payer / Category</td>
                        <td class="val">{category}</td>
                    </tr>
                    <tr>
                        <td class="field">Shifted From</td>
                        <td class="val">{shift_from}</td>
                        <td class="field">Room Category</td>
                        <td class="val">{shift_to}</td>
                    </tr>
                    <tr>
                        <td class="field">Remarks</td>
                        <td class="val" colspan="3">{remark}</td>
                    </tr>
                </table>
                <div class="signatures">
                    <div class="sig-box">Patient / Attendant Signature</div>
                    <div class="sig-box">Authorized Bed Manager Sign</div>
                </div>
            </div>
            <div class="validity-footer">
                ⚠️ IMPORTANT NOTICE: This receipt is valid for TODAY ONLY ({date_str}).
            </div>
        </div>
    </div>
</body>
</html>"""

# --- SIMPLE, FLAT MATTE INTERFACE (NO GLOW, NO BACKGROUND IMAGE ON APP) ---
st.markdown("""
<style>
    .stAppDeployButton, a[href*="github.com"], [data-testid="stSourceCodeLink"] {
        display: none !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: #0b0f19 !important;
        background-image: none !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: #2563eb !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 6px !important;
        padding: 0.5rem 1.1rem !important;
        font-weight: 600 !important;
        box-shadow: none !important;
        text-shadow: none !important;
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        background: #1d4ed8 !important;
        border-color: #60a5fa !important;
        box-shadow: none !important;
    }
    [data-testid="stMetric"], .stForm, .stExpander {
        background: #111827 !important; 
        border: 1px solid #1f2937 !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        margin-bottom: 16px !important;
    }
    h1, h2, h3 {
        color: #f8fafc !important;
        text-shadow: none !important;
    }
    div[role="radiogroup"] {
        gap: 8px !important;
    }
    div[role="radiogroup"] > label {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        padding: 5px 14px !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
    .status-pill-bar {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
    }
    .status-pill {
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }
    .pill-all  { background: #0284c7; color: #ffffff; }
    .pill-wait { background: #272015; color: #fbbf24; border: 1px solid #b45309; }
    .pill-hold { background: #231636; color: #c084fc; border: 1px solid #7e22ce; }
    .pill-done { background: #0f2922; color: #34d399; border: 1px solid #059669; }
    .pill-ward { background: #172554; color: #60a5fa; border: 1px solid #2563eb; }
    [data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1f2937;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. SECURE DATABASE CONNECTION ---
@st.cache_resource
def get_db():
    if "textkey" in st.secrets:
        try:
            raw_key = st.secrets["textkey"]
            key_dict = json.loads(raw_key) if isinstance(raw_key, str) else dict(raw_key)
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds)
        except Exception as e:
            st.error(f"⚠️ Firebase Initialization Error: {e}")
            return None
    st.error("⚠️ Missing 'textkey' in Streamlit Secrets.")
    return None

db = get_db()

# --- 2. BED STRUCTURE & SMART BED MATCHER ---
bed_structure = {
    "Eighth Floor - B Wing": ["B-D-8006", "B-P-8007", "B-P-8008", "B-P-8009", "B-P-8010 SLEEP STUDY", "B-SP-8001-1", "B-SP-8001-2", "B-SP-8002-1", "B-SP-8002-2", "B-SP-8003-1", "B-SP-8003-2", "B-SP-8004-1", "B-SP-8004-2", "B-SP-8005-1", "B-SP-8005-2"],
    "Ninth Floor - A Wing": ["A-P-9001", "A-P-9002", "A-P-9003", "A-P-9004", "A-P-9005 DELUX", "A-SP-9006-1 NEUTROPHILIC", "A-SP-9006-2 NEUTROPHILIC", "A-SP-9007-1", "A-SP-9007-2", "A-SP-9008-1", "A-SP-9008-2", "A-SP-9009-1", "A-SP-9009-2", "A-SP-9010-1", "A-SP-9010-2"],
    "Ninth Floor - B Wing": ["B-D-9020", "B-P-9021", "B-P-9022", "B-P-9023", "B-P-9024", "B-SP-9015-1", "B-SP-9015-2", "B-SP-9016-1", "B-SP-9016-2", "B-SP-9017-1", "B-SP-9017-2", "B-SP-9018-1", "B-SP-9018-2", "B-SP-9019-1", "B-SP-9019-2"],
    "Ninth Floor - C Wing": ["C-D-9036", "C-D-9037", "C-D-9038", "C-D-9039", "C-D-9040", "C-P-9032", "C-P-9033", "C-P-9034", "C-P-9035", "C-P-9041-1", "C-P-9041-2"],
    "Ninth Floor - F Wing": ["F-D-9052", "F-P-9048", "F-P-9049", "F-P-9050", "F-P-9051", "F-SP-9053-1", "F-SP-9053-2", "F-SP-9054-1", "F-SP-9054-2", "F-SP-9055-1", "F-SP-9055-2", "F-SP-9056-1", "F-SP-9056-2", "F-SP-9057-1", "F-SP-9057-2"]
}
all_bed_ids = [b for w in bed_structure.values() for b in w]

def normalize_bed_id(raw_val):
    if pd.isna(raw_val):
        return None
    val = str(raw_val).strip().upper()
    if not val or "OPD" in val:
        return None
    for b in all_bed_ids:
        if val == b.upper():
            return b
    for b in all_bed_ids:
        base_code = b.split(" ")[0].upper()
        if val == base_code or val.startswith(base_code) or base_code in val:
            return b
    return None

# --- 3. FAILSAFE DATA FETCH (IST Timezone Standardized) ---
ist_tz = pytz.timezone('Asia/Kolkata')
today_ist = datetime.now(ist_tz)
today_date_str = today_ist.strftime('%d/%m/%Y')
current_time_str = today_ist.strftime('%I:%M %p')

if db:
    if 'cached_live_data' not in st.session_state or 'cached_req_list' not in st.session_state or 'cached_book_list' not in st.session_state:
        status_doc = db.collection("settings").document("dashboard_status").get()
        st.session_state.is_live = status_doc.to_dict().get("status", "LIVE") if status_doc.exists else "LIVE"
        
        docs = db.collection("beds").stream()
        st.session_state.cached_live_data = {doc.id: doc.to_dict() for doc in docs}
        
        reqs_stream = db.collection("bed_requests").limit(150).stream()
        raw_reqs = []
        for r in reqs_stream:
            data = r.to_dict()
            ts = data.get('timestamp')
            if ts:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                data['timestamp'] = ts
            raw_reqs.append({**data, 'ID': r.id}) 
            
        st.session_state.cached_req_list = sorted(
            raw_reqs,
            key=lambda x: (
                x.get('position', 999),
                PRIORITY_CONFIG.get(x.get('priority', 'STANDARD'), PRIORITY_CONFIG['STANDARD'])['weight'],
                x.get('timestamp', today_ist)
            )
        )
        
        book_stream = db.collection("future_bookings").order_by("book_date", direction=firestore.Query.ASCENDING).stream()
        st.session_state.cached_book_list = [{**b.to_dict(), 'ID': b.id} for b in book_stream]
        
    live_data = st.session_state.cached_live_data
    req_list = st.session_state.cached_req_list
    book_list = st.session_state.cached_book_list

    # --- AUTO-ALLOTMENT CHECKER ---
    needs_rerun = False
    for req in req_list:
        if req.get('status') in ["WAITING", "HOLD"] and req.get('scheduled_time') and req.get('scheduled_bed'):
            try:
                s_time = datetime.fromisoformat(req['scheduled_time'])
                if today_ist >= s_time:
                    db.collection("bed_requests").document(req['ID']).update({
                        "status": "DONE",
                        "bed_no": req['scheduled_bed'],
                        "scheduled_time": "", 
                        "scheduled_bed": ""
                    })
                    db.collection("beds").document(req['scheduled_bed']).set({
                        "status": "ALLOTTED", 
                        "patient": req.get('name', 'Auto-Allotted'),
                        "dr_name": req.get('dr_name', ''),
                        "payer": req.get('category', ''),
                        "uhid": req.get('uhid', '')
                    }, merge=True)
                    needs_rerun = True
            except Exception:
                pass

    if needs_rerun:
        for key in ['cached_live_data', 'cached_req_list']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

else:
    st.error("Database Connection Failed."); st.stop()

# --- 4. SIDEBAR (ADMIN AUTH, FUTURE BOOKING VIEW & EXCEL AUTO-SYNC) ---
show_dashboard = False
with st.sidebar:
    st.header("🛡️ Admin Panel")
    admin_pwd = st.text_input("Admin Password", type="password")
    if admin_pwd == "GeimsAdmin99":
        show_dashboard = True

        # --- ADMIN-ONLY FUTURE BOOKING CONTROL & FULL VIEW ---
        st.subheader("📅 Future Booking Control")
        with st.expander("➕ Add Future Booking", expanded=False):
            with st.form("future_form", clear_on_submit=True):
                f_name = st.text_input("Patient Name *")
                f_uhid = st.text_input("UHID No.")
                f_dr = st.text_input("Doctor Name")
                f_date = st.date_input("Booking Date")
                f_room = st.text_input("Pre-decided Bed ID")
                f_cat = st.selectbox("Category", ["SELF PAY", "ECHS", "CGHS", "TPA", "AYUSHMAN", "OTHER"])
                f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
                if st.form_submit_button("Save Booking"):
                    if f_name.strip():
                        db.collection("future_bookings").add({
                            "name": f_name.strip(),
                            "uhid": f_uhid.strip(),
                            "dr": f_dr.strip(),
                            "book_date": f_date.strftime('%Y-%m-%d'),
                            "category": f_cat,
                            "preference": f_pref,
                            "pref_bed": f_room.strip()
                        })
                        send_ntfy_notification(
                            title="📅 New Future Booking",
                            message=f"Patient: {f_name}\nDate: {f_date.strftime('%d/%m/%Y')}\nDoctor: {f_dr}",
                            priority="urgent",
                            tags="calendar,hospital"
                        )
                        if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                        st.rerun()
                    else:
                        st.warning("Please enter Patient Name.")

        with st.expander(f"📋 Scheduled Future Bookings ({len(book_list)})", expanded=True):
            if book_list:
                for b in book_list:
                    st.markdown(
                        f"<div style='background:#1e293b; border:1px solid #334155; padding:8px 10px; border-radius:6px; margin-bottom:6px; font-size:12px; color:#f8fafc;'>"
                        f"<b>👤 {b.get('name', '-')}</b> (UHID: {b.get('uhid') or '-'})<br>"
                        f"📅 <b>Date:</b> {b.get('book_date', '-')} | 🛏️ <b>Pref:</b> {b.get('preference', '-')} ({b.get('pref_bed') or 'Any'})<br>"
                        f"👨‍⚕️ <b>Dr:</b> {b.get('dr') or '-'} | 💳 <b>Cat:</b> {b.get('category', '-')}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    b_col1, b_col2 = st.columns(2)
                    if b_col1.button("✅ Admit", key=f"adm_sb_{b['ID']}"):
                        db.collection("bed_requests").add({
                            "timestamp": datetime.now(ist_tz),
                            "name": b.get('name'), "uhid": b.get('uhid', ''),
                            "category": b.get('category', 'OTHER'),
                            "dr_name": b.get('dr'), "shift_from": "BOOKING", "shift_to": b.get('preference', 'PRIVATE'),
                            "priority": "IMPORTANT",
                            "remark": f"Reserved: {b.get('pref_bed','-')}",
                            "bed_no": "", "status": "WAITING",
                            "date": today_date_str, "position": 999
                        })
                        db.collection("future_bookings").document(b['ID']).delete()
                        for k in ['cached_req_list', 'cached_book_list']:
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()
                    if b_col2.button("🗑️ Delete", key=f"del_sb_{b['ID']}"):
                        db.collection("future_bookings").document(b['ID']).delete()
                        if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                        st.rerun()
            else:
                st.caption("No upcoming bookings scheduled.")

        # --- SMART EXCEL / CSV AUTO-SYNC ENGINE ---
        st.divider()
        st.subheader("⚡ Smart Excel Bed Auto-Sync")
        st.caption("Upload Occupancy Excel/CSV to auto-fill occupied beds, remove OPD rows, and vacate discharged beds.")
        uploaded_census = st.file_uploader("Upload Occupancy Sheet (.xlsx / .csv)", type=["xlsx", "xls", "csv"])
        
        if uploaded_census is not None:
            try:
                if uploaded_census.name.lower().endswith(".csv"):
                    df_raw = pd.read_csv(uploaded_census)
                else:
                    df_raw = pd.read_excel(uploaded_census)
                
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                cols_list = list(df_raw.columns)

                def guess_col(keywords, default_idx=0):
                    for idx, c in enumerate(cols_list):
                        if any(k in c.lower() for k in keywords):
                            return idx
                    return min(default_idx, len(cols_list) - 1)

                with st.expander("🔧 Verify / Map Excel Columns", expanded=False):
                    bed_col = st.selectbox("Bed Number Column", cols_list, index=guess_col(["bed", "room", "ward_bed"]))
                    pat_col = st.selectbox("Patient Name Column", cols_list, index=guess_col(["patient", "pat_name", "name"], 1))
                    dr_col = st.selectbox("Doctor Name Column", cols_list, index=guess_col(["doc", "consultant", "dr", "physician"], 2))
                    pay_col = st.selectbox("Payer / Category Column", cols_list, index=guess_col(["payer", "category", "tpa", "company", "sponsor", "panel"], 3))
                    uhid_col = st.selectbox("UHID Column (Optional)", ["None"] + cols_list, index=0)
                    type_col = st.selectbox("Visit Type / Ward Column (For OPD Filter)", ["Auto-Detect Across Row"] + cols_list, index=0)

                vacate_missing = st.checkbox("Auto-vacate previously ALLOTTED beds not in this Excel", value=True)

                if st.button("🚀 Sync Beds with Excel Now", use_container_width=True):
                    occupied_map = {}
                    opd_skipped = 0

                    for _, row in df_raw.iterrows():
                        if type_col != "Auto-Detect Across Row":
                            row_type_str = str(row.get(type_col, "")).upper()
                        else:
                            row_type_str = " ".join(str(v).upper() for v in row.values if pd.notna(v))
                        
                        if re.search(r'\b(OPD|OUTPATIENT|OUT-PATIENT)\b', row_type_str):
                            opd_skipped += 1
                            continue

                        raw_bed = row.get(bed_col)
                        matched_bed = normalize_bed_id(raw_bed)
                        p_val = str(row.get(pat_col, "")).strip() if pd.notna(row.get(pat_col)) else ""

                        if not matched_bed or not p_val or p_val.lower() in ["nan", "none", "vacant", ""]:
                            continue

                        dr_val = str(row.get(dr_col, "")).strip() if pd.notna(row.get(dr_col)) else "-"
                        pay_val = str(row.get(pay_col, "")).strip() if pd.notna(row.get(pay_col)) else "-"
                        uhid_val = str(row.get(uhid_col, "")).strip() if (uhid_col != "None" and pd.notna(row.get(uhid_col))) else ""

                        occupied_map[matched_bed] = {
                            "status": "ALLOTTED",
                            "patient": p_val,
                            "dr_name": dr_val,
                            "payer": pay_val,
                            "uhid": uhid_val,
                            "last_sync": today_ist.strftime('%d/%m/%Y %I:%M %p')
                        }

                    batch = db.batch()
                    updated_cnt = 0
                    vacated_cnt = 0

                    for b_id in all_bed_ids:
                        doc_ref = db.collection("beds").document(b_id)
                        if b_id in occupied_map:
                            batch.set(doc_ref, occupied_map[b_id])
                            updated_cnt += 1
                        elif vacate_missing:
                            curr_state = live_data.get(b_id, {}).get("status", "VACANT")
                            if curr_state in ["ALLOTTED", "DISCHARGE"]:
                                batch.set(doc_ref, {"status": "VACANT", "patient": "", "dr_name": "", "payer": "", "uhid": ""})
                                vacated_cnt += 1

                    batch.commit()
                    if 'cached_live_data' in st.session_state:
                        del st.session_state['cached_live_data']
                    st.success(f"✅ Synced! {updated_cnt} Occupied | {vacated_cnt} Vacated | {opd_skipped} OPD Skipped.")
                    st.rerun()

            except Exception as e:
                st.error(f"⚠️ Excel Processing Error: {e}")

        st.divider(); st.subheader("📋 Reports")
        report_data = []
        for idx, r in enumerate(req_list):
            ts = r.get('timestamp')
            if ts:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is None: ts = pytz.utc.localize(ts)
                ts_ist = ts.astimezone(ist_tz)
                ts_str = ts_ist.strftime('%d/%m/%Y %I:%M:%S %p')
            else: ts_str = "-"
            report_data.append({
                "S.N": idx + 1,
                "PRIORITY": r.get('priority', 'STANDARD'),
                "NAME": r.get('name', '-'),
                "UHID": r.get('uhid', '-'),
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
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_report.to_excel(writer, sheet_name="Handover Report", index=False)
        st.download_button(label="📥 Download Handover Summary", data=buffer.getvalue(), file_name=f"Handover_{today_date_str.replace('/', '-')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.divider(); st.subheader("↕️ Manual List Reordering & Priority")
        if req_list:
            reorder_p = st.selectbox("Select Patient to Move / Prioritize", [r.get('name', '') for r in req_list], key="reorder_sel")
            new_pos = st.number_input("New Position Number (1, 2, 3...)", min_value=1, value=1, step=1)
            new_prio = st.selectbox("Update Priority Tag", ["KEEP CURRENT", "VIP", "HWC", "GEU", "IMPORTANT", "STANDARD"])
            if st.button("Apply Position / Priority Change"):
                target_r = next(r for r in req_list if r.get('name') == reorder_p)
                if new_prio != "KEEP CURRENT":
                    db.collection("bed_requests").document(target_r['ID']).update({"priority": new_prio})
                sorted_list = [i for i in req_list if i['ID'] != target_r['ID']]
                sorted_list.insert(int(new_pos) - 1, target_r)
                batch = db.batch()
                for idx, r in enumerate(sorted_list):
                    batch.update(db.collection("bed_requests").document(r['ID']), {"position": idx + 1})
                batch.commit()
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.success(f"Updated {reorder_p} to Position {new_pos}"); st.rerun()

        st.divider(); st.subheader("🔄 Bed & Status Alteration")
        if req_list:
            alt_p = st.selectbox("Select Patient to Alter", [r.get('name', '') for r in req_list], key="alt_p_sel")
            c1, c2 = st.columns(2)
            new_b = c1.selectbox("New Bed ID", [""] + all_bed_ids)
            new_s = c2.selectbox("Alter Status", ["DONE", "WAITING", "CANCELLED", "HOLD", "GEN-WARD ALLOTTED"])
            if st.button("Apply Alteration"):
                p_data = next(r for r in req_list if r.get('name') == alt_p)
                old_bed = p_data.get('bed_no')
                db.collection("bed_requests").document(p_data['ID']).update({"status": new_s, "bed_no": new_b, "scheduled_time": "", "scheduled_bed": ""})
                if old_bed in all_bed_ids:
                    db.collection("beds").document(old_bed).set({"status": "VACANT", "patient": "", "dr_name": "", "payer": "", "uhid": ""})
                if new_b and new_b in all_bed_ids:
                    db.collection("beds").document(new_b).set({
                        "status": "ALLOTTED",
                        "patient": alt_p,
                        "dr_name": p_data.get('dr_name', ''),
                        "payer": p_data.get('category', ''),
                        "uhid": p_data.get('uhid', '')
                    })
                st.success(f"Updated {alt_p} successfully.")
                for k in ['cached_req_list', 'cached_live_data']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

        st.divider(); st.subheader("⏳ Schedule Auto-Allotment")
        waiting_patients = [r.get('name', '') for r in req_list if r.get('status') in ['WAITING', 'HOLD']]
        if waiting_patients:
            sched_p = st.selectbox("Select Waiting/Hold Patient", waiting_patients, key="sched_p_sel")
            sched_b = st.selectbox("Select Target Bed", all_bed_ids, key="sched_b_sel")
            sched_t = st.time_input("Scheduled Auto-Allot Time", value=today_ist.time(), key="sched_t_input")
            
            if st.button("Set Auto-Allot Timer"):
                p_data = next(r for r in req_list if r.get('name') == sched_p)
                s_dt = datetime.combine(today_ist.date(), sched_t)
                s_dt = ist_tz.localize(s_dt)
                
                db.collection("bed_requests").document(p_data['ID']).update({
                    "scheduled_time": s_dt.isoformat(),
                    "scheduled_bed": sched_b
                })
                st.success(f"Timer set for {sched_p} on Bed {sched_b}.")
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()
        else:
            st.info("No waiting or hold patients available to schedule.")

        st.divider(); st.subheader("📝 Entry Modification")
        if req_list:
            target = st.selectbox("Select Patient to Edit", [r.get('name', '') for r in req_list], key="sb_mod")
            action = st.radio("Action", ["Edit Remark", "Mark as CANCELLED", "Delete Entry", "Clear Auto-Timer"], horizontal=True)
            new_val = st.text_input("New Remark (If Editing)")
            if st.button("Confirm Modification"):
                r_id = next(r['ID'] for r in req_list if r.get('name') == target)
                if action == "Delete Entry": db.collection("bed_requests").document(r_id).delete()
                elif action == "Mark as CANCELLED": db.collection("bed_requests").document(r_id).update({"status": "CANCELLED", "bed_no": "", "scheduled_time": "", "scheduled_bed": ""})
                elif action == "Clear Auto-Timer": db.collection("bed_requests").document(r_id).update({"scheduled_time": "", "scheduled_bed": ""})
                else: db.collection("bed_requests").document(r_id).update({"remark": new_val})
                if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                st.rerun()

        st.divider(); st.subheader("⚙️ Manual Bed Update")
        m_bed = st.selectbox("Select Bed ID", all_bed_ids)
        m_stat = st.selectbox("Status", ["VACANT", "BOOKED", "ALLOTTED", "DISCHARGE", "MAINTENANCE", "RESTRICTED"])
        m_name = st.text_input("Patient Name Override")
        m_dr = st.text_input("Doctor Name Override")
        m_pay = st.text_input("Payer / Category Override")
        if st.button("Apply Bed Update"):
            db.collection("beds").document(m_bed).set({
                "status": m_stat,
                "patient": m_name if m_stat != "VACANT" else "",
                "dr_name": m_dr if m_stat != "VACANT" else "",
                "payer": m_pay if m_stat != "VACANT" else ""
            }, merge=True)
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
            st.rerun()

        st.divider(); st.error("⚠️ DATA RESET")
        if st.button("RESET ALL BEDS"):
            batch = db.batch()
            for b in all_bed_ids:
                batch.set(db.collection("beds").document(b), {"status": "VACANT", "patient": "", "dr_name": "", "payer": "", "uhid": ""})
            batch.commit()
            if 'cached_live_data' in st.session_state: del st.session_state['cached_live_data']
            st.rerun()

# --- 5. CLEAN SIMPLE HEADER ---
st.markdown("<h1 style='text-align: center; margin-bottom: 4px;'>GEIMS Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #94a3b8; margin-top: 0;'><b>Current Date: {today_date_str}</b></p>", unsafe_allow_html=True)

if st.button("🔄 Refresh Dashboard Data"):
    for key in ['cached_live_data', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 6. ADMIN-ONLY TODAY'S BOOKING ALERTS ---
if show_dashboard:
    today_iso = today_ist.strftime('%Y-%m-%d')
    alerts = [b for b in book_list if b.get('book_date') == today_iso]
    for a in alerts:
        with st.container():
            st.markdown(f"<div style='background-color: #2a141b; border: 1px solid #e11d48; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; color: #fecdd3;'><b>🚨 TODAY'S SCHEDULED BOOKING (ADMIN VIEW): {a.get('name', 'N/A')} | UHID: {a.get('uhid', '-')} | Doctor: {a.get('dr', '-')} | Preferred Bed: {a.get('pref_bed', '-')}</b></div>", unsafe_allow_html=True)
            if st.button(f"✅ Admit Booking: {a.get('name')}", key=f"ack_{a['ID']}"):
                db.collection("bed_requests").add({
                    "timestamp": datetime.now(ist_tz),
                    "name": a.get('name'), "uhid": a.get('uhid', ''),
                    "category": a.get('category', 'OTHER'),
                    "dr_name": a.get('dr'), "shift_from": "BOOKING", "shift_to": a.get('preference', 'PRIVATE'), 
                    "priority": "IMPORTANT",
                    "remark": f"Reserved: {a.get('pref_bed','-')}",
                    "bed_no": "", "status": "WAITING", 
                    "date": today_date_str, "position": 999
                })
                send_ntfy_notification(
                    title="🚨 Booking Admitted",
                    message=f"Patient: {a.get('name')}\nCategory: {a.get('category', 'OTHER')}\nDoctor: {a.get('dr')}",
                    priority="urgent",
                    tags="inbox_tray,hospital"
                )
                db.collection("future_bookings").document(a['ID']).delete()
                for k in ['cached_req_list', 'cached_book_list']: 
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

# --- 7. PATIENT SHIFTING & PRIORITY QUEUE REGISTRATION ---
with st.expander("📋 PATIENT SHIFTING & PRIORITY QUEUE MANAGEMENT", expanded=True):
    total_cnt = len(req_list)
    wait_cnt = sum(1 for r in req_list if r.get('status', 'WAITING') == "WAITING" and not r.get('bed_no'))
    hold_cnt = sum(1 for r in req_list if r.get('status') == "HOLD")
    done_cnt = sum(1 for r in req_list if r.get('status') == "DONE" or (r.get('bed_no') and r.get('status') in ["WAITING", "HOLD"]))
    ward_cnt = sum(1 for r in req_list if r.get('status') == "GEN-WARD ALLOTTED")

    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding-bottom:12px; border-bottom:1px solid #1f2937; margin-bottom:16px;">
        <div>
            <div style="font-size:1.15rem; font-weight:700; color:#f8fafc;">
                Patient Shifting & Priority Queue Registration
            </div>
            <div style="font-size:0.82rem; color:#94a3b8;">
                Register patient admissions & transfers. Priority tags organize internal queue order.
            </div>
        </div>
        <div class="status-pill-bar">
            <span class="status-pill pill-all">All ({total_cnt})</span>
            <span class="status-pill pill-wait">⏳ Waiting ({wait_cnt})</span>
            <span class="status-pill pill-hold">⏸️ Hold ({hold_cnt})</span>
            <span class="status-pill pill-done">✅ Allotted ({done_cnt})</span>
            <span class="status-pill pill-ward">🏥 Gen-Ward ({ward_cnt})</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("new_req", clear_on_submit=True):
        r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns([2.1, 1.3, 1.5, 1.6, 1.4, 1.4])
        p_name = r1c1.text_input("PATIENT NAME *", placeholder="Enter Registered Patient Name")
        p_uhid = r1c2.text_input("UHID (OPTIONAL)", placeholder="Only if available")
        p_cat = r1c3.selectbox("PAYER / CATEGORY", ["SELF PAY", "ECHS", "UPCL", "UJVN", "CGHS CASH", "BHEL", "ONGC", "TPA", "CGHS", "ICAR", "AYUSHMAN", "OTHER"])
        dr_name = r1c4.text_input("DOCTOR NAME *", placeholder="Admitting Doctor")
        p_fr = r1c5.selectbox("SHIFT FROM", ["EMERGENCY", "CCU", "DELUXE", "PVT", "SEMI PVT", "HDU", "OPD", "ICU", "WARD", "LR", "OTHER"])
        p_to = r1c6.selectbox("SHIFTING TO", ["PRIVATE", "DELUXE", "SEMI-PRIVATE", "GEN-WARD"])

        r2c1, r2c2, r2c3 = st.columns([3.8, 3.2, 2.3])
        p_prio = r2c1.radio(
            "PRIORITY TAG (INTERNAL QUEUE ORDER)",
            ["VIP", "HWC", "GEU", "IMPORTANT", "STANDARD"],
            index=4,
            horizontal=True
        )
        rem = r2c2.text_input("CLINICAL REMARK / URGENCY REASON", placeholder="Clinical condition, room preference note...")
        with r2c3:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            submit_req = st.form_submit_button("➕ Submit Shifting Request", use_container_width=True)

        if submit_req:
            if not p_name.strip() or not dr_name.strip():
                st.warning("⚠️ Please enter both **Patient Name** and **Doctor Name**.")
            else:
                p_name_clean = p_name.strip().lower()
                p_dr_clean = dr_name.strip().lower()
                is_duplicate = False
                
                for r in req_list:
                    db_name = str(r.get('name') or "").strip().lower()
                    db_dr = str(r.get('dr_name') or "").strip().lower()
                    if (db_name == p_name_clean and 
                        r.get('category') == p_cat and 
                        db_dr == p_dr_clean and 
                        r.get('shift_from') == p_fr and 
                        r.get('shift_to') == p_to and 
                        r.get('status') in ["WAITING", "HOLD"]):
                        is_duplicate = True
                        break
                        
                if is_duplicate:
                    st.warning("⚠️ Duplicate Entry: An identical active shifting request already exists in the queue.")
                else:
                    db.collection("bed_requests").add({
                        "timestamp": datetime.now(ist_tz), 
                        "name": p_name.strip(),
                        "uhid": p_uhid.strip(),
                        "category": p_cat,
                        "dr_name": dr_name.strip(),
                        "shift_from": p_fr,
                        "shift_to": p_to,
                        "priority": p_prio,
                        "remark": rem.strip(),
                        "bed_no": "",
                        "status": "WAITING",
                        "date": today_date_str,
                        "position": 999
                    })
                    
                    send_ntfy_notification(
                        title=f"🏥 [{p_prio}] New Shifting Request",
                        message=f"Patient: {p_name}\nUHID: {p_uhid or '-'}\nPayer: {p_cat}\nDoctor: {dr_name}\nShift: {p_fr} ➡️ {p_to}",
                        priority="urgent",
                        tags="bell,bed"
                    )

                    if 'cached_req_list' in st.session_state: del st.session_state['cached_req_list']
                    st.rerun()

    # Queue Filtering & Clean List
    if req_list:
        st.divider()
        fc1, fc2, fc3, fc4 = st.columns(4)
        sq = fc1.text_input("🔍 Search Patient / UHID / Doctor", "").lower()
        prio_filter = fc2.selectbox("🏷️ Filter by Priority Tag", ["ALL", "VIP", "HWC", "GEU", "IMPORTANT", "STANDARD"])
        shift_filter = fc3.selectbox("📂 Filter by Room Preference", ["ALL", "DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        status_filter = fc4.selectbox("📊 Filter by Status", ["ALL", "WAITING", "DONE", "CANCELLED", "HOLD", "GEN-WARD ALLOTTED"])

        st.divider()
        h_cols = st.columns([0.5, 1.1, 2.0, 1.2, 1.4, 1.2, 1.2, 1.8, 1.0, 1.2, 1.2])
        headers = ["S.N", "TAG", "PATIENT / UHID", "PAYER", "DOCTOR", "FROM", "TO", "REMARK", "BED", "STATUS", "RECEIPT"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        
        for idx, r in enumerate(req_list):
            current_status = r.get('status', 'WAITING')
            b_no = r.get('bed_no', '')
            if b_no and current_status in ["WAITING", "HOLD"]:
                current_status = "DONE"
            prio_tag = r.get('priority', 'STANDARD')
            if prio_tag not in PRIORITY_CONFIG:
                prio_tag = "STANDARD"
            p_style = PRIORITY_CONFIG[prio_tag]

            searchable_blob = f"{r.get('name','')} {r.get('uhid','')} {r.get('dr_name','')}".lower()
            name_match = sq in searchable_blob
            prio_match = (prio_filter == "ALL") or (prio_tag == prio_filter)
            room_match = (shift_filter == "ALL") or (r.get('shift_to') == shift_filter)
            status_match = (status_filter == "ALL") or (current_status == status_filter)
            
            if not (name_match and prio_match and room_match and status_match):
                continue

            ts = r.get('timestamp')
            if ts:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is None: ts = pytz.utc.localize(ts)
                ts_str = ts.astimezone(ist_tz).strftime('%d/%m/%Y %I:%M:%S %p')
            else:
                ts_str = "-"

            r_cols = st.columns([0.5, 1.1, 2.0, 1.2, 1.4, 1.2, 1.2, 1.8, 1.0, 1.2, 1.2])
            r_cols[0].write(f"**{idx + 1}**")
            r_cols[1].markdown(
                f"<span style='background:{p_style['bg']}; color:{p_style['color']}; border:1px solid {p_style['border']}; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:700;'>{prio_tag}</span>",
                unsafe_allow_html=True
            )
            uhid_sub = f"<br><span style='font-size:11px; color:#94a3b8;'>UHID: {r.get('uhid')}</span>" if r.get('uhid') else ""
            r_cols[2].markdown(f"<b>{r.get('name', '-')}</b>{uhid_sub}", unsafe_allow_html=True)
            r_cols[3].write(r.get('category', '-'))
            r_cols[4].write(r.get('dr_name', '-'))
            r_cols[5].write(r.get('shift_from', '-'))
            r_cols[6].write(r.get('shift_to', '-'))
            r_cols[7].write(r.get('remark', '-') or "-")
            r_cols[8].write(f"**{b_no}**" if b_no else "-")

            color_map = {"DONE": "#10b981", "CANCELLED": "#ef4444", "GEN-WARD ALLOTTED": "#3b82f6", "HOLD": "#a855f7"}
            color = color_map.get(current_status, "#f59e0b")
            
            if r.get('scheduled_time') and current_status in ["WAITING", "HOLD"]:
                s_t = r.get('scheduled_time')
                html_code = f"""
                <!DOCTYPE html><html><head><style>
                    body {{ margin: 0; padding: 0; font-family: sans-serif; font-size: 13px; font-weight: bold; color: {color}; background: transparent; overflow: hidden; }}
                    .t {{ font-size: 11px; color: #fde047; font-weight: 600; display: block; margin-top: 2px; }}
                </style></head><body>
                    <div id="main_{r['ID']}">{current_status}</div>
                    <script>
                        const end = new Date("{s_t}").getTime();
                        const el = document.getElementById("main_{r['ID']}");
                        const timer = setInterval(() => {{
                            const dist = end - new Date().getTime();
                            if (dist < 0) {{
                                clearInterval(timer);
                                el.innerHTML = "{current_status}<br><span class='t'>⏳ Auto-Allot Ready!</span>";
                            }} else {{
                                const h = Math.floor((dist % (1000*60*60*24)) / (1000*60*60));
                                const m = Math.floor((dist % (1000*60*60)) / (1000*60));
                                const s = Math.floor((dist % (1000*60)) / 1000);
                                el.innerHTML = "{current_status}<br><span class='t'>⏳ " + h + "h " + m + "m " + s + "s</span>";
                            }}
                        }}, 1000);
                    </script>
                </body></html>
                """
                with r_cols[9]:
                    components.html(html_code, height=42)
            else:
                r_cols[9].markdown(f"<span style='color:{color}; font-weight:700;'>{current_status}</span>", unsafe_allow_html=True)
            
            # Official Printable HTML Receipt (With GEIMS Background, No Priority, Valid Today Only)
            if current_status == "DONE":
                receipt_html = generate_advanced_receipt_html(r, today_date_str, current_time_str)
                r_cols[10].download_button(
                    "🖨️ Receipt",
                    data=receipt_html,
                    file_name=f"GEIMS_Receipt_{r.get('name', 'Patient').replace(' ', '_')}.html",
                    mime="text/html",
                    key=f"rec_{r['ID']}"
                )

            # Neutral Entry Timestamp (Zero Priority Reflection)
            st.markdown(
                f"<div style='font-size: 11px; color: #94a3b8; margin-left: 35px; margin-top: -10px; margin-bottom: 10px;'>🕒 Entry Timestamp (IST): <b>{ts_str}</b></div>",
                unsafe_allow_html=True
            )

# --- PDF CONSENT FORM PANEL ---
st.subheader("📝 ADMISSION & SHIFTING CONSENT FORMS (PDF)")

def get_pdf_data(file_name):
    try:
        with open(file_name, "rb") as f: return f.read()
    except FileNotFoundError: return None

c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns(5)
with c_col1: st.download_button("💳 1 - SELF PAY", get_pdf_data("consent_self_pay.pdf") or b"", file_name="Consent_SelfPay.pdf", mime="application/pdf")
with c_col2: st.download_button("💰 2 - CGHS CASH", get_pdf_data("consent_cghs_cash.pdf") or b"", file_name="Consent_CGHS_Cash.pdf", mime="application/pdf")
with c_col3: st.download_button("🎖️ 3 - ECHS", get_pdf_data("consent_echs.pdf") or b"", file_name="Consent_ECHS.pdf", mime="application/pdf")
with c_col4: st.download_button("🏥 4 - CGHS CREDIT/PSU", get_pdf_data("consent_cghs_credit.pdf") or b"", file_name="Consent_CGHS_Credit.pdf", mime="application/pdf")
with c_col5: st.download_button("🏢 5 - TPA", get_pdf_data("consent_tpa.pdf") or b"", file_name="Consent_TPA.pdf", mime="application/pdf")

# --- 8. VISUAL LIVE BED DASHBOARD ---
if show_dashboard:
    status_colors = {
        "VACANT": "#FFFFFF",
        "BOOKED": "#DCFCE7",
        "ALLOTTED": "#1E293B",
        "DISCHARGE": "#E0F2FE",
        "MAINTENANCE": "#E2E8F0",
        "RESTRICTED": "#FEE2E2"
    }
    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing)
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": "", "dr_name": "", "payer": ""})
            st_val = data.get("status", "VACANT")
            bg = status_colors.get(st_val, "#FFFFFF")
            txt = "#FFFFFF" if st_val == "ALLOTTED" else ("#991B1B" if st_val == "RESTRICTED" else "#0F172A")
            border_css = "1px solid #475569" if st_val == "ALLOTTED" else "1px solid #CBD5E1"

            pat_line = f"<b>{data.get('patient', '')}</b>" if data.get('patient') else "<i>Available</i>"
            dr_line = f"<br><span style='font-size:9.5px; opacity:0.85;'>👨‍⚕️ {data.get('dr_name')}</span>" if data.get('dr_name') else ""
            pay_line = f"<br><span style='font-size:9px; border:1px solid rgba(148,163,184,0.4); padding:1px 5px; border-radius:4px;'>💳 {data.get('payer')}</span>" if data.get('payer') else ""

            with cols[i % 5]:
                st.markdown(
                    f'<div style="background-color:{bg}; color:{txt}; padding:7px 5px; border:{border_css}; border-radius:6px; text-align:center; height:110px; font-size:11px; margin-bottom:8px;">'
                    f'<b style="font-size:11.5px;">{bed}</b><br>'
                    f'<span style="font-size:9.5px; font-weight:700;">{st_val}</span><br>'
                    f'<span style="font-size:10.5px;">{pat_line}</span>'
                    f'{dr_line}{pay_line}'
                    f'</div>',
                    unsafe_allow_html=True
                )
else:
    st.info("🔒 Enter Admin Password in sidebar to view Bed Status, Future Bookings & Excel Auto-Sync.")
