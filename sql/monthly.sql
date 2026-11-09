SELECT substr(b.arrival_date, 1, 7) AS arrival_month,
       COUNT(*) AS bookings, SUM(b.is_canceled) AS cancellations,
       1.0 * SUM(b.is_canceled) / COUNT(*) AS cancellation_rate,
       COALESCE(SUM(b.revenue_proxy), 0.0) AS checkout_revenue_proxy
FROM bookings b
WHERE (:supplier_id IS NULL OR b.supplier_id = :supplier_id)
  AND (:arrival_year IS NULL OR b.arrival_year = :arrival_year)
GROUP BY substr(b.arrival_date, 1, 7)
ORDER BY arrival_month;
