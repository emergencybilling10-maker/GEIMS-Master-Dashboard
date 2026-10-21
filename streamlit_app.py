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

# --- PRIORITY WEIGHTS & STYLING CONFIG ---
PRIORITY_CONFIG = {
    "VIP":       {"weight": 1, "color": "#FFD700", "bg": "rgba(255, 215, 0, 0.14)",  "border": "rgba(255, 215, 0, 0.7)",  "glow": "0 0 18px rgba(255, 215, 0, 0.45)", "icon": "👑"},
    "HWC":       {"weight": 2, "color": "#00E5FF", "bg": "rgba(0, 229, 255, 0.14)",  "border": "rgba(0, 229, 255, 0.7)",  "glow": "0 0 18px rgba(0, 229, 255, 0.45)", "icon": "⚕️"},
    "GEU":       {"weight": 3, "color": "#00E676", "bg": "rgba(0, 230, 118, 0.14)",  "border": "rgba(0, 230, 118, 0.7)",  "glow": "0 0 18px rgba(0, 230, 118, 0.45)", "icon": "🏛️"},
    "IMPORTANT": {"weight": 4, "color": "#FF5252", "bg": "rgba(255, 82, 82, 0.14)",  "border": "rgba(255, 82, 82, 0.7)",  "glow": "0 0 18px rgba(255, 82, 82, 0.45)", "icon": "🔥"},
    "STANDARD":  {"weight": 5, "color": "#94A3B8", "bg": "rgba(15, 23, 42, 0.55)",   "border": "rgba(255, 255, 255, 0.15)", "glow": "none", "icon": "🔹"}
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

# --- QUANTUM FLUID + DARK CYBER-GLASS UI ---
st.markdown("""
<style>
    .stAppDeployButton, a[href*="github.com"], [data-testid="stSourceCodeLink"] {
        display: none !important;
    }
    [data-testid="stAppViewContainer"] {
        background-image: url("https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTNqazRwZDFlMjcwaTl6OHlvY21ucGd3YWoxaWYycjVsaG1jeGhmbyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/U4ExkAvRpVQGB0NMe0/giphy.gif") !important;
        background-size: cover !important;
        background-position: center !important;
        background-attachment: fixed !important;
    }
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(6, 11, 25, 0.72); 
        z-index: 0;
        pointer-events: none;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(90deg, #00c6ff 0%, #5b247a 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(0, 229, 255, 0.5) !important;
        border-radius: 12px !important;
        padding: 0.65rem 1.5rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.8px;
        box-shadow: 0 4px 20px rgba(0, 198, 255, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(0, 229, 255, 0.6) !important;
    }
    [data-testid="stMetric"], .stForm, .stExpander {
        background: rgba(13, 18, 36, 0.82) !important; 
        backdrop-filter: blur(28px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 18px !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65) !important;
        z-index: 1;
        margin-bottom: 20px !important;
    }
    /* Radio Horizontal Pill Buttons for Priority Tag */
    div[role="radiogroup"] {
        gap: 10px !important;
    }
    div[role="radiogroup"] > label {
        background: rgba(15, 23, 42, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 10px !important;
        padding: 8px 20px !important;
        color: #e2e8f0 !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
    }
    div[role="radiogroup"] > label:hover {
        border-color: #00e5ff !important;
        box-shadow: 0 0 12px rgba(0, 229, 255, 0.35) !important;
    }
    h1 {
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 0 4px 15px rgba(0,0,0,0.7);
        text-align: center;
        letter-spacing: 2px;
    }
    .status-pill-bar {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        justify-content: flex-end;
        align-items: center;
    }
    .status-pill {
        padding: 6px 15px;
        border-radius: 999px;
        font-size: 12.5px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        letter-spacing: 0.4px;
    }
    .pill-all { background: #00bcd4; color: #001f24; box-shadow: 0 0 12px rgba(0,188,212,0.4); }
    .pill-wait { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.45); }
    .pill-hold { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.45); }
    .pill-done { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.45); }
    .pill-ward { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.45); }
    [data-testid="stSidebar"] {
        background-color: rgba(6, 10, 22, 0.92) !important;
        backdrop-filter: blur(24px);
        border-right: 1px solid rgba(255, 255, 255, 0.12);
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
    """Matches HIS Excel bed codes (e.g. 'B-P-8010' or '9005') to exact master bed IDs."""
    if pd.isna(raw_val):
        return None
    val = str(raw_val).strip().upper()
    if not val or "OPD" in val:
        return None
    # 1. Exact match
    for b in all_bed_ids:
        if val == b.upper():
            return b
    # 2. Prefix base code match (e.g., 'B-P-8010' -> 'B-P-8010 SLEEP STUDY')
    for b in all_bed_ids:
        base_code = b.split(" ")[0].upper()
        if val == base_code or val.startswith(base_code) or base_code in val:
            return b
    return None

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
            
        # Sort by: 1) Manual Position (if set < 999), 2) Priority Weight (VIP=1 -> STANDARD=5), 3) Timestamp
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

# --- 4. HEADER ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Bed Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><b>Current Date: {today_date_str}</b></p>", unsafe_allow_html=True)

if st.button("🔄 Refresh Dashboard Data"):
    for key in ['cached_live_data', 'cached_req_list', 'cached_book_list']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- 5. TODAY'S BOOKING ALERTS ---
today_iso = today_ist.strftime('%Y-%m-%d')
alerts = [b for b in book_list if b.get('book_date') == today_iso]
for a in alerts:
    with st.container():
        st.markdown(f"<div style='background-color: rgba(255, 82, 82, 0.2); border: 2px solid #FF5252; padding: 15px; border-radius: 10px; margin-bottom: 8px; color: white;'><b>🚨 TODAY'S BOOKING: {a.get('name', 'N/A')} | UHID: {a.get('uhid', '-')} | Preferred: {a.get('pref_bed', '-')}</b></div>", unsafe_allow_html=True)
        if st.button(f"✅ Admit: {a.get('name')}", key=f"ack_{a['ID']}"):
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

# --- 6. ADVANCED PATIENT SHIFTING & PRIORITY QUEUE REGISTRATION ---
with st.expander("✨ PATIENT SHIFTING & PRIORITY QUEUE MANAGEMENT", expanded=True):
    # Live Pill Counters
    total_cnt = len(req_list)
    wait_cnt = sum(1 for r in req_list if r.get('status', 'WAITING') == "WAITING" and not r.get('bed_no'))
    hold_cnt = sum(1 for r in req_list if r.get('status') == "HOLD")
    done_cnt = sum(1 for r in req_list if r.get('status') == "DONE" or (r.get('bed_no') and r.get('status') in ["WAITING", "HOLD"]))
    ward_cnt = sum(1 for r in req_list if r.get('status') == "GEN-WARD ALLOTTED")

    # Screenshot-matched Header + Dynamic Status Pill Badges
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding-bottom:14px; border-bottom:1px solid rgba(255,255,255,0.12); margin-bottom:18px;">
        <div>
            <div style="font-size:1.35rem; font-weight:800; color:#ffffff; display:flex; align-items:center; gap:8px;">
                ✨ Patient Shifting & Priority Queue Registration
            </div>
            <div style="font-size:0.84rem; color:#94a3b8; margin-top:2px;">
                Register real patient admissions & transfers only. Prioritized cases (VIP, HWC, GEU, Important) glow prominently.
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

    # Registration Form matching the exact 2-row dark layout
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
            "GLOWING PRIORITY TAG (VIP, HWC, GEU, IMPORTANT, STANDARD)",
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

    # Queue Filtering & Glowing Priority Cards
    if req_list:
        st.divider()
        fc1, fc2, fc3, fc4 = st.columns(4)
        sq = fc1.text_input("🔍 Search Patient / UHID / Doctor", "").lower()
        prio_filter = fc2.selectbox("✨ Filter by Priority Tag", ["ALL", "VIP", "HWC", "GEU", "IMPORTANT", "STANDARD"])
        shift_filter = fc3.selectbox("📂 Filter by Room Preference", ["ALL", "DELUXE", "PRIVATE", "SEMI-PRIVATE", "GEN-WARD"])
        status_filter = fc4.selectbox("📊 Filter by Status", ["ALL", "WAITING", "DONE", "CANCELLED", "HOLD", "GEN-WARD ALLOTTED"])

        st.divider()
        h_cols = st.columns([0.5, 1.1, 2.0, 1.3, 1.4, 1.3, 1.3, 1.8, 1.0, 1.2, 1.1])
        headers = ["S.N", "PRIORITY", "PATIENT / UHID", "PAYER", "DOCTOR", "FROM", "TO", "REMARK", "BED", "STATUS", "SLIP"]
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
                ts_str = ts.astimezone(ist_tz).strftime('%d/%m/%Y %I:%M %p')
            else:
                ts_str = "-"

            # Glowing Priority Wrapper Banner for VIP / HWC / GEU / IMPORTANT
            if prio_tag != "STANDARD":
                st.markdown(
                    f"<div style='background:{p_style['bg']}; border-left:4px solid {p_style['color']}; border-top:1px solid {p_style['border']}; box-shadow:{p_style['glow']}; padding:4px 12px; border-radius:8px; margin-bottom:4px; font-size:11.5px; color:{p_style['color']}; font-weight:700;'>"
                    f"{p_style['icon']} {prio_tag} PRIORITY CASE &nbsp;|&nbsp; 🕒 Logged: {ts_str}</div>",
                    unsafe_allow_html=True
                )

            r_cols = st.columns([0.5, 1.1, 2.0, 1.3, 1.4, 1.3, 1.3, 1.8, 1.0, 1.2, 1.1])
            r_cols[0].write(f"**{idx + 1}**")
            r_cols[1].markdown(
                f"<span style='background:{p_style['bg']}; color:{p_style['color']}; border:1px solid {p_style['border']}; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800;'>{p_style['icon']} {prio_tag}</span>",
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
                    .t {{ font-size: 11px; color: #ffeb3b; font-weight: 600; display: block; margin-top: 2px; }}
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
                r_cols[9].markdown(f"<span style='color:{color}; font-weight:800;'>{current_status}</span>", unsafe_allow_html=True)
            
            if current_status == "DONE":
                slip = (
                    f"====================================\n"
                    f"      G.E.I.M.S (Bed Management)\n"
                    f"      BED ALLOTMENT SLIP\n"
                    f"====================================\n"
                    f"DATE:     {today_date_str}\n"
                    f"PATIENT:  {r.get('name', '')}\n"
                    f"UHID:     {r.get('uhid', '-')}\n"
                    f"PRIORITY: {prio_tag}\n"
                    f"DOCTOR:   {r.get('dr_name', '-')}\n"
                    f"PAYER:    {r.get('category', '-')}\n"
                    f"------------------------------------\n"
                    f"BED:      {b_no}\n"
                    f"===================================="
                )
                r_cols[10].download_button("🖨️ Slip", data=slip, file_name=f"Slip_{r.get('name', 'Patient')}.txt", key=f"rec_{r['ID']}")

            if prio_tag == "STANDARD":
                st.markdown(f"<div style='font-size: 11px; color: rgba(255,255,255,0.55); margin-left: 35px; margin-top: -10px; margin-bottom: 10px;'>🕒 Entry Timestamp (IST): <b>{ts_str}</b></div>", unsafe_allow_html=True)

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

# --- 7. SIDEBAR & SMART EXCEL CENSUS SYNC ---
show_dashboard = False
with st.sidebar:
    st.header("📅 Future Booking Control")
    with st.expander("📝 ADD FUTURE BOOKING"):
        with st.form("future_form", clear_on_submit=True):
            f_name = st.text_input("Patient Name"); f_uhid = st.text_input("UHID No."); f_dr = st.text_input("Doctor Name")
            f_date = st.date_input("Booking Date"); f_room = st.text_input("Pre-decided Bed ID"); f_cat = st.selectbox("Category", ["SELF PAY", "OTHER"]); f_pref = st.selectbox("Bed Preference", ["DELUXE", "PRIVATE", "SEMI-PRIVATE"])
            if st.form_submit_button("Save"):
                db.collection("future_bookings").add({"name": f_name, "uhid": f_uhid, "dr": f_dr, "book_date": f_date.strftime('%Y-%m-%d'), "category": f_cat, "preference": f_pref, "pref_bed": f_room})
                send_ntfy_notification(
                    title="📅 New Future Booking",
                    message=f"Patient: {f_name}\nDate: {f_date.strftime('%d/%m/%Y')}\nDoctor: {f_dr}",
                    priority="urgent",
                    tags="calendar,hospital"
                )
                if 'cached_book_list' in st.session_state: del st.session_state['cached_book_list']
                st.rerun()

    st.divider(); st.header("🛡️ Admin Panel")
    if st.text_input("Admin Password", type="password") == "GeimsAdmin99":
        show_dashboard = True

        # --- NEW: SMART EXCEL / CSV AUTO-SYNC ENGINE ---
        st.subheader("⚡ Smart Excel Bed Auto-Sync")
        st.caption("Upload HIS Occupancy Excel/CSV. Automatically removes OPD rows, fills occupied beds (Patient, Doctor, Payer), and vacates discharged beds.")
        uploaded_census = st.file_uploader("Upload Occupancy Sheet (.xlsx / .csv)", type=["xlsx", "xls", "csv"])
        
        if uploaded_census is not None:
            try:
                if uploaded_census.name.lower().endswith(".csv"):
                    df_raw = pd.read_csv(uploaded_census)
                else:
                    df_raw = pd.read_excel(uploaded_census)
                
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                cols_list = list(df_raw.columns)

                # Helper to auto-detect column names from HIS export
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

                vacate_missing = st.checkbox("Auto-vacate previously ALLOTTED beds not present in this Excel (Discharged)", value=True)

                if st.button("🚀 Sync Beds with Excel Now", use_container_width=True):
                    occupied_map = {}
                    opd_skipped = 0
                    unmatched_beds = []

                    for _, row in df_raw.iterrows():
                        # 1. Strip out OPD / Emergency / Casualty encounters automatically
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

                        if not matched_bed:
                            if pd.notna(raw_bed) and str(raw_bed).strip():
                                unmatched_beds.append(str(raw_bed).strip())
                            continue

                        if not p_val or p_val.lower() in ["nan", "none", "vacant", ""]:
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

                    # 2. Batch Commit to Firestore
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
                            # Only auto-vacate beds that were ALLOTTED or DISCHARGE (preserve MAINTENANCE, RESTRICTED, BOOKED)
                            if curr_state in ["ALLOTTED", "DISCHARGE"]:
                                batch.set(doc_ref, {"status": "VACANT", "patient": "", "dr_name": "", "payer": "", "uhid": ""})
                                vacated_cnt += 1

                    batch.commit()
                    if 'cached_live_data' in st.session_state:
                        del st.session_state['cached_live_data']
                    st.success(f"✅ Synced! {updated_cnt} Beds Occupied | {vacated_cnt} Discharged/Vacated | {opd_skipped} OPD Rows Ignored.")
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

# --- 8. VISUAL LIVE BED DASHBOARD (ENHANCED WITH DOCTOR & PAYER) ---
if show_dashboard:
    status_colors = {
        "VACANT": "#FFFFFF",
        "BOOKED": "#90EE90",
        "ALLOTTED": "#0F172A",
        "DISCHARGE": "#ADD8E6",
        "MAINTENANCE": "#E0E0E0",
        "RESTRICTED": "#FF0000"
    }
    st.title("🏥 Live Bed Status")
    for wing, beds in bed_structure.items():
        st.subheader(wing)
        cols = st.columns(5)
        for i, bed in enumerate(beds):
            data = live_data.get(bed, {"status": "VACANT", "patient": "", "dr_name": "", "payer": ""})
            st_val = data.get("status", "VACANT")
            bg = status_colors.get(st_val, "#FFFFFF")
            txt = "white" if st_val in ["ALLOTTED", "RESTRICTED"] else "#0f172a"
            border_css = "2px solid #00e5ff" if st_val == "ALLOTTED" else "1px solid #ccc"

            pat_line = f"<b>{data.get('patient', '')}</b>" if data.get('patient') else "<i>Available</i>"
            dr_line = f"<br><span style='font-size:9.5px; opacity:0.85;'>👨‍⚕️ {data.get('dr_name')}</span>" if data.get('dr_name') else ""
            pay_line = f"<br><span style='font-size:9px; background:rgba(0,229,255,0.2); padding:1px 5px; border-radius:4px;'>💳 {data.get('payer')}</span>" if data.get('payer') else ""

            with cols[i % 5]:
                st.markdown(
                    f'<div style="background-color:{bg}; color:{txt}; padding:7px 5px; border:{border_css}; border-radius:8px; text-align:center; height:112px; font-size:11px; margin-bottom:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">'
                    f'<b style="font-size:11.5px;">{bed}</b><br>'
                    f'<span style="font-size:9.5px; font-weight:800; letter-spacing:0.5px;">{st_val}</span><br>'
                    f'<span style="font-size:10.5px;">{pat_line}</span>'
                    f'{dr_line}{pay_line}'
                    f'</div>',
                    unsafe_allow_html=True
                )
else:
    st.info("🔒 Enter Admin Password in sidebar to view Bed Status & Excel Auto-Sync.")
