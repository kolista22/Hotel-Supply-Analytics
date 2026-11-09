import sqlite3
import json
import pyarrow as pa
import unittest
from streamlit.testing.v1 import AppTest
from analytics import ROOT, query

class DashboardSmokeTest(unittest.TestCase):
    def test_startup_and_filter_recalculate_metrics(self):
        app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        with sqlite3.connect(ROOT/"data/bookings.sqlite") as conn:
            count=int(query(conn,"overview").iloc[0].bookings)
            city=int(query(conn,"overview","synthetic_city").iloc[0].bookings)
        self.assertEqual(app.metric[0].value,f"{count:,}")
        self.assertTrue(any("SYNTHETIC" in item.value for item in app.warning))
        app.selectbox[0].select("Synthetic City Demo").run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.metric[0].value,f"{city:,}")

if __name__ == "__main__":unittest.main()

class ChartRegressionTest(unittest.TestCase):
    def test_trend_has_real_numeric_points_and_temporal_axis_for_filters(self):
        app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=20).run()
        for group,year in [("All supply groups","All years"),("All supply groups",2016),("Synthetic City Demo",2016),("Synthetic Resort Demo",2016)]:
            app.selectbox[0].select(group);app.selectbox[1].select(year);app.run()
            self.assertEqual(len(app.exception),0)
            charts=app.get("vega_lite_chart")
            spec=json.loads(charts[-1].proto.spec)
            self.assertEqual(spec["encoding"]["x"]["type"],"temporal")
            self.assertEqual(spec["encoding"]["y"]["type"],"quantitative")
            self.assertNotIn("params",spec)
            def frame(chart):
                data=chart.proto.data.data or chart.proto.datasets[0].data.data
                return pa.ipc.open_stream(data).read_all().to_pandas()
            trend=frame(charts[-1]);comparison=frame(charts[0])
            self.assertEqual(len(comparison),2)
            self.assertEqual(len(trend),26 if year=="All years" else 12)
            self.assertTrue(trend.bookings.gt(0).all())
            self.assertTrue(trend.arrival_month.is_monotonic_increasing)
            self.assertEqual(trend.bookings.sum(),int(app.metric[0].value.replace(",","")))
            with sqlite3.connect(ROOT/"data/bookings.sqlite") as conn:
                expected=query(conn,"suppliers",None,None if year=="All years" else year)
            self.assertEqual(comparison.bookings.sum(),expected.bookings.sum())
