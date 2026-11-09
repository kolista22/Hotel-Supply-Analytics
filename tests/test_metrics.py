import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from analytics import ROOT, clean_bookings, write_database, query, insights


def fixture():
    rows = []
    for hotel, canceled, status, nights, adr, year in [
        ("Resort Hotel", 0, "Check-Out", 2, 100, 2016),
        ("Resort Hotel", 1, "Canceled", 4, 90, 2016),
        ("City Hotel", 0, "Check-Out", 3, 80, 2017),
        ("City Hotel", 1, "No-Show", 1, 70, 2016),
        ("City Hotel", 0, "Check-Out", 0, 50, 2016),
        ("City Hotel", 0, "Check-Out", 1, -5, 2016),
    ]:
        rows.append(dict(hotel=hotel, is_canceled=canceled, reservation_status=status,
            stays_in_weekend_nights=0, stays_in_week_nights=nights, adr=adr,
            arrival_date_year=year, arrival_date_month="July", arrival_date_day_of_month=1))
    return pd.DataFrame(rows)

class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name)/"test.sqlite"
        self.clean, self.audit = clean_bookings(fixture())
        write_database(self.clean,self.db)
        self.conn=sqlite3.connect(self.db)
    def tearDown(self):
        self.conn.close();self.tmp.cleanup()
    def test_known_booking_rate_and_value_proxy(self):
        row=query(self.conn,"overview").iloc[0]
        self.assertEqual(row.bookings,6);self.assertEqual(row.cancellations,2)
        self.assertAlmostEqual(row.cancellation_rate,2/6)
        self.assertEqual(row.checkout_revenue_proxy,440)
        self.assertEqual(row.proxy_eligible_bookings,2)
    def test_join_counts_and_weighted_rate_reconcile(self):
        groups=query(self.conn,"suppliers");overall=query(self.conn,"overview").iloc[0]
        self.assertEqual(groups.bookings.sum(),overall.bookings)
        self.assertEqual(groups.checkout_revenue_proxy.sum(),overall.checkout_revenue_proxy)
        self.assertAlmostEqual(groups.cancellations.sum()/groups.bookings.sum(),overall.cancellation_rate)
        self.assertNotAlmostEqual(groups.cancellation_rate.mean(),overall.cancellation_rate)
        self.assertTrue(groups.is_synthetic.eq(1).all())
    def test_bound_filters_and_empty_selection(self):
        row=query(self.conn,"overview","synthetic_resort",2016).iloc[0]
        self.assertEqual(row.bookings,2);self.assertEqual(row.cancellation_rate,.5)
        empty=query(self.conn,"overview","not-a-group",2016)
        self.assertEqual(empty.iloc[0].bookings,0);self.assertTrue(pd.isna(empty.iloc[0].cancellation_rate))
        self.assertEqual(len(insights(empty,query(self.conn,"suppliers","not-a-group"),query(self.conn,"monthly","not-a-group"))),1)
    def test_monthly_totals_reconcile(self):
        month=query(self.conn,"monthly");self.assertEqual(month.bookings.sum(),6);self.assertEqual(month.checkout_revenue_proxy.sum(),440)
    def test_duplicates_are_reported_not_silently_removed(self):
        raw=pd.concat([fixture(),fixture().iloc[[0]]],ignore_index=True)
        clean,audit=clean_bookings(raw)
        self.assertEqual(len(clean),7);self.assertEqual(audit["exact_duplicate_rows"],1)
    def test_missing_fields_and_invalid_core_rows(self):
        with self.assertRaises(ValueError):clean_bookings(fixture().drop(columns="adr"))
        bad=fixture().iloc[[0,0,0]].copy();bad.iloc[0,bad.columns.get_loc("is_canceled")]=2
        bad.iloc[1,bad.columns.get_loc("stays_in_week_nights")]=-1
        bad.iloc[2,bad.columns.get_loc("hotel")]="Unknown Hotel"
        clean,audit=clean_bookings(pd.concat([fixture(),bad],ignore_index=True))
        self.assertEqual(len(clean),6);self.assertEqual(audit["excluded_invalid_core_rows"],3)
    def test_bad_rates_are_excluded_from_proxy_not_volume(self):
        raw=fixture();raw["adr"]=raw["adr"].astype(float);raw.loc[0,"adr"]=float("inf");raw.loc[2,"adr"]=None
        clean,audit=clean_bookings(raw)
        self.assertEqual(len(clean),6);self.assertEqual(audit["missing_or_nonfinite_adr_rows"],2)
        self.assertEqual(clean.revenue_proxy.notna().sum(),0)

class RealDataTest(unittest.TestCase):
    def test_real_csv_pandas_and_sql_reconcile(self):
        raw=pd.read_csv(ROOT/"data/hotels.csv",na_values=["NULL","NA"])
        clean,_=clean_bookings(raw)
        with sqlite3.connect(ROOT/"data/bookings.sqlite") as conn:
            overall=query(conn,"overview").iloc[0];groups=query(conn,"suppliers");monthly=query(conn,"monthly")
        self.assertEqual(overall.bookings,len(clean))
        self.assertEqual(overall.cancellations,clean.is_canceled.sum())
        self.assertAlmostEqual(overall.cancellation_rate,clean.is_canceled.mean())
        self.assertAlmostEqual(overall.checkout_revenue_proxy,clean.revenue_proxy.sum(),places=5)
        self.assertEqual(groups.bookings.sum(),overall.bookings)
        self.assertEqual(monthly.bookings.sum(),overall.bookings)
        self.assertEqual(groups.cancellations.sum(),overall.cancellations)

if __name__ == "__main__": unittest.main()
