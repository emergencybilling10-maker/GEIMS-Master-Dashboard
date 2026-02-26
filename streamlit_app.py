import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="GEIMS Official Billing Tool", layout="wide", page_icon="🏥")

# --- SMART DATA LOADING ---
@st.cache_data(ttl=60)
def load_geims_data():
    try:
        # Loading the database.csv you just uploaded
        df = pd.read_csv("database.csv")
        
        # FIX FOR THE "REINDEXING" ERROR: Standardize duplicate column names
        cols = []
        count = {}
        for col in df.columns:
            col_name = str(col).strip()
            if col_name in count:
                count[col_name] += 1
                cols.append(f"{col_name}_{count[col_name]}")
            else:
                count[col_name] = 0
                cols.append(col_name)
        df.columns = cols
        return df
    except Exception as e:
        st.error(f"Error loading database.csv: {e}")
        return None

df_master = load_geims_data()

# GEIMS 2025 Policy: Fixed Rates for EXTRA days beyond package
# These apply only if stay > Pkg Days
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
        st.info("Policy: Packages include Room, Diet, Nursing, and RMO for Pkg Days.")

    try:
        # Dynamic Selection Logic
        col1, col2 = st.columns(2)
        
        # Automatically find the Department and Service columns
        dept_col = [c for c in df_master.columns if 'dept' in c.lower()][0]
        serv_col = [c for c in df_master.columns if 'service' in c.lower() or 'procedure' in c.lower()][0]
        
        with col1:
            sel_dept = st.selectbox("Search Department", sorted(df_master[dept_col].dropna().unique()))
        with col2:
            procs = sorted(df_master[df_master[dept_col] == sel_dept][serv_col].dropna().unique())
            sel_proc = st.selectbox("Select Procedure / Investigation", procs)

        # Pull correct row
        row = df_master[df_master[serv_col] == sel_proc]
        
        # Find the price column that matches your room category
        price_col = [c for c in df_master.columns if room_cat.lower() in c.lower()][0]
        price_val = str(row[price_col].values[0]).replace(',', '').replace('₹', '').strip()
        base_rate = float(price_val) if price_val.replace('.','').isdigit() else 0.0
        
        # Package Days detection (finds columns like 'Pkg Days' or 'Days')
        pkg_day_col = [c for c in df_master.columns if 'day' in c.lower() and ('pkg' in c.lower() or 'package' in c.lower())]
        pkg_days = int(row[pkg_day_col[0]].values[0]) if pkg_day_col else 1
        
        # GEIMS Policy Math
        extra_days = max(0, total_stay - pkg_days)
        r = ROOM_POLICY[room_cat]

        breakdown = {
            f"Package Base Rate ({sel_proc})": base_rate,
            "Package Inclusions": f"Includes Room, Diet, Nursing & RMO for {pkg_days} days",
            "Admission / MRD Fee": 450.0  # Fixed as per GEIMS 2025 Manual
        }

        if extra_days > 0:
            breakdown[f"Extra Room & Nursing ({extra_days} days)"] = float((r['Rent'] + r['Nursing'] + r['RMO']) * extra_days)
            breakdown[f"Extra Consultation (2 visits/day)"] = float((r['Consult'] * 2) * extra_days)
            breakdown[f"Extra Diet Charges"] = float(r['Diet'] * extra_days)

        st.markdown("---")
        st.subheader(f"Formal Estimate for: {pat_name}")
        st.table(pd.DataFrame(list(breakdown.items()), columns=["Description", "Amount (₹)"]))
        
        total_cost = sum([v for v in breakdown.values() if isinstance(v, (float, int))])
        st.metric("Total Estimated Bill", f"₹ {total_cost:,.2f}")
        st.caption("Note: Implants, Pharmacy, and Consumables are extra as per actuals.")

    except Exception as e:
        st.error(f"Mapping Error: Please check if your CSV headers match 'Department' and 'Service Name'. Detail: {e}")
else:
    st.warning("🔄 System is ready. Ensure 'database.csv' is uploaded and matches headers.")
