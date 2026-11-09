"""Small, traceable CSV -> pandas -> SQLite descriptive analytics pipeline."""
from pathlib import Path
import hashlib
import json
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
SUPPLIERS = {"Resort Hotel": ("synthetic_resort", "Synthetic Resort Demo"), "City Hotel": ("synthetic_city", "Synthetic City Demo")}
REQUIRED = {"hotel", "is_canceled", "arrival_date_year", "arrival_date_month", "arrival_date_day_of_month", "stays_in_weekend_nights", "stays_in_week_nights", "adr", "reservation_status"}
MONTHS = {name: i for i, name in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}

def clean_bookings(raw):
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    df = raw.copy()
    report = {"raw_rows": len(df), "raw_columns": list(df.columns), "missing_by_column": {c: int(v) for c, v in df.isna().sum().items()}, "exact_duplicate_rows": int(df.duplicated().sum()), "duplicate_policy": "Retained: source has no unique booking identifier; identical rows may be distinct bookings."}
    df["source_row"] = range(1, len(df) + 1)
    df["hotel"] = df.hotel.astype("string").str.strip()
    for c in ["is_canceled", "arrival_date_year", "arrival_date_day_of_month", "stays_in_weekend_nights", "stays_in_week_nights", "adr"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    month = df.arrival_date_month.astype("string").str.strip().map(MONTHS)
    date = pd.to_datetime(dict(year=df.arrival_date_year, month=month, day=df.arrival_date_day_of_month), errors="coerce")
    weekends, weekdays = df.stays_in_weekend_nights, df.stays_in_week_nights
    valid = df.hotel.isin(SUPPLIERS) & df.is_canceled.isin([0, 1]) & date.notna() & weekends.ge(0) & weekdays.ge(0) & weekends.mod(1).eq(0) & weekdays.mod(1).eq(0)
    report["excluded_invalid_core_rows"] = int((~valid).sum())
    df = df.loc[valid].copy()
    df["arrival_date"] = date.loc[valid].dt.strftime("%Y-%m-%d")
    df["arrival_year"] = date.loc[valid].dt.year.astype(int)
    df["nights"] = (df.stays_in_weekend_nights + df.stays_in_week_nights).astype(int)
    df["supplier_id"] = df.hotel.map(lambda h: SUPPLIERS[h][0])
    df["is_canceled"] = df.is_canceled.astype(int)
    df["adr"] = df.adr.where(df.adr.notna() & df.adr.abs().lt(float("inf")))
    report["negative_adr_rows"] = int(df.adr.lt(0).sum())
    report["missing_or_nonfinite_adr_rows"] = int(df.adr.isna().sum())
    report["zero_night_rows"] = int(df.nights.eq(0).sum())
    eligible = df.is_canceled.eq(0) & df.reservation_status.eq("Check-Out") & df.nights.gt(0) & df.adr.ge(0)
    df["revenue_proxy"] = (df.adr * df.nights).where(eligible)
    report["clean_rows"] = len(df)
    report["proxy_eligible_rows"] = int(eligible.sum())
    report["proxy_excluded_rows"] = int((~eligible).sum())
    report["arrival_start"] = df.arrival_date.min() if len(df) else None
    report["arrival_end"] = df.arrival_date.max() if len(df) else None
    return df[["source_row", "hotel", "supplier_id", "arrival_date", "arrival_year", "is_canceled", "reservation_status", "nights", "adr", "revenue_proxy"]], report

def write_database(clean, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destination) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DROP TABLE IF EXISTS bookings")
        conn.execute("DROP TABLE IF EXISTS suppliers")
        conn.execute("CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, label TEXT NOT NULL, hotel_type TEXT NOT NULL UNIQUE, is_synthetic INTEGER NOT NULL CHECK(is_synthetic=1))")
        conn.executemany("INSERT INTO suppliers VALUES (?, ?, ?, 1)", [(v[0], v[1], k) for k, v in SUPPLIERS.items()])
        conn.execute("""CREATE TABLE bookings (
          source_row INTEGER PRIMARY KEY, hotel TEXT NOT NULL, supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
          arrival_date TEXT NOT NULL, arrival_year INTEGER NOT NULL, is_canceled INTEGER NOT NULL CHECK(is_canceled IN (0,1)),
          reservation_status TEXT, nights INTEGER NOT NULL CHECK(nights>=0), adr REAL, revenue_proxy REAL CHECK(revenue_proxy IS NULL OR revenue_proxy>=0))""")
        columns = list(clean.columns)
        values = clean.astype(object).where(pd.notna(clean), None)
        conn.executemany("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)", values.itertuples(index=False, name=None))
        conn.execute("CREATE INDEX idx_bookings_filters ON bookings(supplier_id, arrival_year)")

def query(conn, name, supplier_id=None, arrival_year=None):
    if name not in {"overview", "suppliers", "monthly"}:
        raise ValueError("Unknown query")
    return pd.read_sql_query((ROOT / "sql" / (name + ".sql")).read_text(), conn, params={"supplier_id": supplier_id, "arrival_year": arrival_year})

def insights(overview, suppliers, monthly):
    row = overview.iloc[0]
    if int(row.bookings) == 0:
        return ["No bookings match these filters; no rate or comparison can be inferred."]
    notes = [f"{int(row.bookings):,} bookings include {int(row.cancellations):,} cancellations ({row.cancellation_rate:.1%}). This is a booking-level proportion, not an average of group rates."]
    if len(suppliers) >= 2:
        low, high = suppliers.loc[suppliers.cancellation_rate.idxmin()], suppliers.loc[suppliers.cancellation_rate.idxmax()]
        notes.append(f"{high['label']} has a {high.cancellation_rate:.1%} cancellation rate versus {low.cancellation_rate:.1%} for {low['label']} ({(high.cancellation_rate-low.cancellation_rate)*100:.1f} percentage points). These are hotel-type groups with synthetic labels, not real supplier rankings or causal effects.")
    if len(monthly):
        peak = monthly.loc[monthly.bookings.idxmax()]
        notes.append(f"The largest observed arrival month in this selection is {peak.arrival_month}, with {int(peak.bookings):,} bookings. This reflects the selected historical sample; boundary years are partial.")
    return notes[:3]

def prepare():
    source = ROOT / "data/hotels.csv"
    if not source.exists():
        raise FileNotFoundError("Run python download_data.py first.")
    meta = json.loads((ROOT / "data/source.json").read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("CSV hash differs from the recorded source; review provenance before processing.")
    raw = pd.read_csv(source, na_values=["NULL", "NA"], keep_default_na=True)
    clean, report = clean_bookings(raw)
    if clean.empty:
        raise ValueError("No valid bookings remain.")
    write_database(clean, ROOT / "data/bookings.sqlite")
    reports = ROOT / "reports"; reports.mkdir(exist_ok=True)
    (reports / "data_quality.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    with sqlite3.connect(ROOT / "data/bookings.sqlite") as conn:
        frames = {name: query(conn, name) for name in ["overview", "suppliers", "monthly"]}
    for name, frame in frames.items():
        frame.to_csv(reports / (name + ".csv"), index=False)
    notes = insights(frames["overview"], frames["suppliers"], frames["monthly"])
    (reports / "observations.md").write_text("# Computed observations\n\n" + "\n\n".join(notes) + "\n")
    return report, frames, notes

if __name__ == "__main__":
    report, frames, notes = prepare()
    print(json.dumps(report, indent=2))
    print(frames["overview"].to_string(index=False))
    print("\n".join(notes))
