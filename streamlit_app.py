import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
import json
from datetime import datetime, timedelta
import pytz
import io

# Page Config
st.set_page_config(page_title="GEIMS Master Bed Tracker", layout="wide")

# --- QUANTUM FLUID + ULTRA-GLASS 3D INTERFACE ---
st.markdown("""
<style>
    /* HIDE STREAMLIT frontend GITHUB CODE DISCOVERY LINK DEPLOY BUTTON OVERLAY */
    .stAppDeployButton, a[href*="github.com"], [data-testid="stSourceCodeLink"] {
        display: none !important;
    }

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
            raw_req
