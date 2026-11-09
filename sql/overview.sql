-- One definition shared by headline metrics. Parameters are bound, not interpolated.
WITH selected AS (
  SELECT * FROM bookings b
  WHERE (:supplier_id IS NULL OR b.supplier_id = :supplier_id)
    AND (:arrival_year IS NULL OR b.arrival_year = :arrival_year)
)
SELECT COUNT(*) AS bookings,
       COALESCE(SUM(is_canceled), 0) AS cancellations,
       1.0 * SUM(is_canceled) / NULLIF(COUNT(*), 0) AS cancellation_rate,
       COALESCE(SUM(revenue_proxy), 0.0) AS checkout_revenue_proxy,
       COUNT(revenue_proxy) AS proxy_eligible_bookings
FROM selected;
