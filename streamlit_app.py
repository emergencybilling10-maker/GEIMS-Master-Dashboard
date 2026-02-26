import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="GEIMS Official Billing Tool", layout="wide", page_icon="🏥")

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_geims_data():
    try:
        # Loading the clean CSV you just converted
        df = pd.read_csv("database.csv")
        # Standardizing headers to remove spaces or hidden characters
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error: Ensure 'database.csv' is in your GitHub. Detail: {e}")
        return None

df_master = load_geims_data()

# GEIMS 2025 Policy: Fixed Rates for EXTRA days beyond package
ROOM_POLICY = {
    "Economy": {"Rent": 2500, "Consult": 700, "Nursing": 500, "Diet": 100, "RMO": 700},
    "Double": {"Rent": 4500, "Consult": 900, "Nursing": 600, "Diet": 100, "RMO": 800},
    "Single/ ICU": {"Rent": 7500, "Consult": 1200, "Nursing": 600, "Diet": 100, "RMO": 800},
    "Classic Deluxe": {"Rent": 10000, "Consult": 1500, "Nursing": 600, "Diet": 100, "RMO": 800},
    "Suite": {"Rent": 33000, "Consult": 2000, "Nursing": 2800, "Diet": 100, "RMO": 3000},
}

st.title("🏥 GEIMS Hospital Official Billing Estimator")
st.subheader("Graphic Era Institute of Medical Sciences | 2026 Ready")

if df_master is not None:
    with st.sidebar:
        st.header("Patient Setup")
        pat_name = st.text_input("Patient Name", value="Anuj Gill") 
        room_cat = st.selectbox("Selected Bed Category", list(ROOM_POLICY.keys()))
        total_stay = st.number_input("Total Days of Stay", min_value=1, value=1)
        st.divider()
        st.info("Policy: Package inclusive of Room, Diet, and Nursing for Pkg Days.")

    try:
        # Dynamic Department and Procedure Selection
        col1, col2 = st.columns(2)
        with col1:
            sel_dept = st.selectbox("Search Department", sorted(df_master['Department'].dropna().unique()))
        with col2:
            procs = sorted(df_master[df_master['Department'] == sel_dept]['Service Name'].dropna().unique())
            sel_proc = st.selectbox("Select Procedure / Investigation", procs)

        # Logic: Pulling the correct row from your CSV
        row = df_master[df_master['Service Name'] == sel_proc]
        
        # Price Cleaning
        price_val = str(row[room_cat].values[0]).replace(',', '').replace('₹', '').strip()
        base_rate = float(price_val) if price_val.replace('.','').isdigit() else 0.0
        
        # Package Days Logic
        pkg_days = int(row['Package Days'].values[0]) if 'Package Days' in df_master.columns else 1
        
        # Extra Day Calculation (GEIMS 11 AM - 11 AM Policy)
        extra_days = max(0, total_stay - pkg_days)
        r = ROOM_POLICY[room_cat]

        # Breakdown table structure
        breakdown = {
            f"Package Rate ({sel_proc})": base_rate,
            "Package Inclusions": f"Includes Room, Diet, Nursing & RMO for {pkg_days} days",
            "Admission / MRD Fee": 450.0  # Fixed as per GEIMS Policy
        }

        if extra_days > 0:
            # Adding daily rates only for days exceeding the package
            breakdown[f"Extra Room & Nursing ({extra_days} days)"] = float((r['Rent'] + r['Nursing'] + r['RMO']) * extra_days)
            breakdown[f"Extra Consultation (2 visits/day)"] = float((r['Consult'] * 2) * extra_days)
            breakdown[f"Extra Diet Charges"] = float(r['Diet'] * extra_days)

        st.markdown("---")
        st.subheader(f"Formal Estimate for: {pat_name}")
        st.table(pd.DataFrame(list(breakdown.items()), columns=["Description", "Amount (₹)"]))
        
        # Total Value Calculation
        total_cost = sum([v for v in breakdown.values() if isinstance(v, (float, int))])
        st.metric("Total Estimated Bill", f"₹ {total_cost:,.2f}")
        st.caption("Note: Implants, Pharmacy, and Consumables are extra as per actuals.")

    except Exception as e:
        st.error(f"Mapping Error: Ensure CSV columns are 'Department', 'Service Name', and 'Package Days'. Detail: {e}")
else:
    st.warning("🔄 System is waiting for 'database.csv' to be uploaded to the repository.")
