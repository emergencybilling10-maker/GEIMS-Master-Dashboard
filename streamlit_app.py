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

# --- ADVANCED PRINTABLE HTML RECEIPT GENERATOR (A3, UPPER-LEFT, CLEAN FIELDS) ---
def generate_advanced_receipt_html(req_data, date_str, generated_time_str):
    patient_name = req_data.get('name', '-')
    uhid = req_data.get('uhid') or 'N/A'
    category = req_data.get('category', '-')
    dr_name = req_data.get('dr_name', '-')
    shift_from = req_data.get('shift_from', '-')
    bed_no = req_data.get('bed_no', '-')
    bg_url = "https://mdmsenquiry.com/wp-content/uploads/2024/07/GEIMS-Dehradun-1.png"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Bed Allotment Receipt - {patient_name}</title>
    <style>
        @page {{
            size: A3;
            margin: 10mm;
        }}
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
            padding: 15px;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: flex-start;
        }}
        .receipt-card {{
            position: relative;
            width: 680px;
            margin: 0;
            background-color: #ffffff;
            border: 2px solid #0f172a;
            border-radius: 8px;
            overflow: hidden;
        }}
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
            padding: 14px 22px;
            border-bottom: 3px solid #2563eb;
            gap: 16px;
        }}
        .header-left h1 {{
            margin: 0;
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .header-left p {{
            margin: 4px 0 0 0;
            font-size: 11.5px;
            color: #cbd5e1;
        }}
        .logo-box {{
            background: #ffffff;
            padding: 4px 6px;
            border-radius: 6px;
            border: 1.5px solid #cbd5e1;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}
        .header-logo {{
            width: 115px;
            height: 54px;
            object-fit: contain;
            display: block;
        }}
        .sub-bar {{
            display: flex;
            justify-content: flex-end;
            background: rgba(248, 250, 252, 0.94);
            padding: 8px 22px;
            border-bottom: 1px solid #cbd5e1;
            font-size: 12px;
            font-weight: 700;
            color: #1e293b;
        }}
        .content {{
            padding: 18px 22px;
        }}
        .bed-highlight {{
            background: rgba(239, 246, 255, 0.94);
            border: 1.5px solid #60a5fa;
            border-radius: 6px;
            padding: 12px 18px;
            margin-bottom: 14px;
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
            font-size: 20px;
            font-weight: 900;
            color: #1e3a8a;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            background: rgba(255, 255, 255, 0.9);
        }}
        td {{
            padding: 9px 12px;
            border: 1px solid #94a3b8;
        }}
        td.field {{
            background: rgba(241, 245, 249, 0.94);
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
        .validity-footer {{
            background: #fef2f2;
            border-top: 2px solid #dc2626;
            color: #991b1b;
            text-align: center;
            padding: 10px 16px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.4px;
        }}
        .print-btn-wrap {{
            margin-bottom: 12px;
        }}
        .print-btn {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 9px 20px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
            font-size: 13px;
        }}
        @media print {{
            html, body {{
                background: #ffffff;
                margin: 0 !important;
                padding: 0 !important;
                align-items: flex-start !important;
                justify-content: flex-start !important;
            }}
            .print-btn-wrap {{
                display: none !important;
            }}
            .receipt-card {{
                margin: 0 !important;
                border: 2px solid #000;
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-btn-wrap">
        <button class="print-btn" onclick="window.print()">🖨️ Print Official Bed Allotment Receipt (A3 Upper-Left)</button>
    </div>
    <div class="receipt-card">
        <div class="receipt-bg"></div>
        <div class="receipt-inner">
            <div class="header">
                <div class="header-left">
                    <h1>Graphic Era Institute of Medical Sciences</h1>
                    <p>IPD Bed Management & Official Allotment Receipt • Dehradun, Uttarakhand</p>
                </div>
                <div class="logo-box">
                    <img class="header-logo" src="{bg_url}" alt="GEIMS Logo">
                </div>
            </div>
            <div class="sub-bar">
                <span>DATE OF ISSUE: {date_str} ({generated_time_str})</span>
            </div>
            <div class="content">
                <div class="bed-highlight">
                    <span class="label">Allotted Ward / Bed Number</span>
                    <span class="value">{bed_no}</span>
                </div>
                <table>
                    <tr>
                        <td class="field
