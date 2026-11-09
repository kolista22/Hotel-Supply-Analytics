from pathlib import Path
import json
import sqlite3
import pandas as pd
import streamlit as st
from analytics import ROOT, query, insights

st.set_page_config(page_title="Hotel Supply Analytics", page_icon="📊", layout="wide")
st.title("Hotel Supply Analytics")
st.caption("Historical booking analysis · Python / pandas / SQLite · local portfolio MVP")
st.warning("SYNTHETIC SUPPLIER MAPPING: Resort Hotel → Synthetic Resort Demo; City Hotel → Synthetic City Demo. These labels are illustrative hotel-type groups, not real suppliers or Nuitée data.")
db = ROOT / "data/bookings.sqlite"
if not db.exists():
    st.error("Local database missing. Run python download_data.py, then python analytics.py from the project directory.")
    st.stop()

@st.cache_data
def read_reports(db_version, supplier_id, year):
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        frames = {name: query(conn, name, supplier_id, year) for name in ["overview", "suppliers", "monthly"]}
        frames["comparison_suppliers"] = query(conn, "suppliers", None, year)
        return frames

try:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        mapping = pd.read_sql_query("SELECT supplier_id, label FROM suppliers ORDER BY label", conn)
        years = pd.read_sql_query("SELECT DISTINCT arrival_year FROM bookings ORDER BY arrival_year", conn).arrival_year.tolist()
    options = {"All supply groups": None, **dict(zip(mapping.label, mapping.supplier_id))}
    left, right = st.columns(2)
    label = left.selectbox("Supply group (synthetic)", list(options))
    year = right.selectbox("Arrival year", ["All years"] + years)
    frames = read_reports(db.stat().st_mtime_ns, options[label], None if year == "All years" else int(year))
    overview, suppliers, monthly = [frames[name] for name in ["overview", "suppliers", "monthly"]]
    comparison_suppliers = frames["comparison_suppliers"]
    row = overview.iloc[0]
except (sqlite3.Error, OSError, ValueError) as exc:
    st.error("Could not read local analysis. Re-run python analytics.py and inspect the local database.")
    st.stop()
cols = st.columns(4)
cols[0].metric("Bookings", f"{int(row.bookings):,}")
cols[1].metric("Cancellation rate", "N/A" if pd.isna(row.cancellation_rate) else f"{row.cancellation_rate:.1%}")
cols[2].metric("Check-out value proxy*", f"{row.checkout_revenue_proxy:,.0f}")
cols[3].metric("Proxy-eligible bookings", f"{int(row.proxy_eligible_bookings):,}")
st.caption("*Sum of ADR × booked nights for non-cancelled Check-Out rows with positive nights and valid nonnegative ADR. ADR currency units; not audited revenue, profit, payment or supplier settlement. No-Show and cancelled rows excluded from this proxy.")
st.caption(f"KPI, observations and trend scope: {label}; arrival year: {year}.")
st.subheader("Computed observations")
for note in insights(overview, suppliers, monthly):
    st.write("• " + note)
st.subheader("Supply-group comparison — synthetic labels")
st.caption(f"Comparison scope: ALL synthetic supply groups; arrival year: {year}. The group filter above applies to KPIs, observations and trend, not these comparison charts. These are not real suppliers.")
a, b = st.columns(2)
a.bar_chart(comparison_suppliers.set_index("label")[["bookings"]], color="#387b75")
b.bar_chart(comparison_suppliers.assign(cancellation_percent=comparison_suppliers.cancellation_rate*100).set_index("label")[["cancellation_percent"]], color="#b96050")
with st.expander("View SQL result tables"):
    st.caption("Comparison table: all synthetic groups in the selected year. Monthly table: selected group and year, matching KPIs.")
    st.dataframe(comparison_suppliers, hide_index=True, width="stretch", column_config={"cancellation_rate": st.column_config.NumberColumn(format="percent")})
    st.dataframe(monthly, hide_index=True, width="stretch")
st.subheader("Arrival-month trend")
if monthly.empty:
    st.info("No monthly bookings match these filters.")
else:
    trend = monthly[["arrival_month", "bookings"]].copy()
    trend["arrival_month"] = pd.to_datetime(trend["arrival_month"], format="%Y-%m", errors="raise")
    trend = trend.sort_values("arrival_month")
    st.vega_lite_chart(trend, {
        "mark": {"type": "line", "point": True, "color": "#387b75"},
        "encoding": {
            "x": {"field": "arrival_month", "type": "temporal", "title": "Arrival month", "axis": {"format": "%Y-%m", "labelAngle": -45}},
            "y": {"field": "bookings", "type": "quantitative", "title": "Bookings", "scale": {"zero": True}},
            "tooltip": [{"field": "arrival_month", "type": "temporal", "format": "%Y-%m"}, {"field": "bookings", "type": "quantitative"}]
        }
    }, height=320, width="stretch")
st.caption("Arrivals July 2015–August 2017. First and last years are incomplete; this is not booking-creation or cancellation-event time.")
with st.expander("Metric definitions & SQL"):
    st.markdown("Booking volume counts retained source rows, including cancellations. Cancellation rate = cancelled bookings / all retained bookings. Identical source rows are retained because no genuine booking ID exists. All views use the same cleaned SQLite table and rate denominator. KPIs/observations/trend use the selected group and year; comparison charts use all groups in the selected year. No causality or actual supplier quality is inferred.")
    for name in ["overview", "suppliers", "monthly"]:
        st.markdown("**"+name+"**")
        st.code((ROOT / "sql" / (name+".sql")).read_text(), language="sql")
with st.expander("Data quality audit — full dataset, not filtered"):
    report_path = ROOT / "reports/data_quality.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        st.json({k:v for k,v in report.items() if k not in ["raw_columns", "missing_by_column"]})
        st.dataframe(pd.DataFrame(report["missing_by_column"].items(), columns=["column", "missing_rows"]), hide_index=True)
    else: st.info("Quality report unavailable. Re-run python analytics.py.")
st.caption("Data: Antonio, de Almeida & Nunes (2019), Hotel booking demand datasets, CC BY 4.0; TidyTuesday CSV mirror. AI-assisted implementation and validation by Codex; user review pending. No affiliation with Nuitée.")
