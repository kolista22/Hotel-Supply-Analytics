-- Synthetic dimension is one-to-one with anonymized hotel type, NOT real suppliers.
SELECT s.supplier_id, s.label, s.hotel_type, s.is_synthetic,
       COUNT(*) AS bookings, SUM(b.is_canceled) AS cancellations,
       1.0 * SUM(b.is_canceled) / COUNT(*) AS cancellation_rate,
       COALESCE(SUM(b.revenue_proxy), 0.0) AS checkout_revenue_proxy,
       COUNT(b.revenue_proxy) AS proxy_eligible_bookings
FROM bookings b JOIN suppliers s ON b.supplier_id = s.supplier_id
WHERE (:supplier_id IS NULL OR b.supplier_id = :supplier_id)
  AND (:arrival_year IS NULL OR b.arrival_year = :arrival_year)
GROUP BY s.supplier_id, s.label, s.hotel_type, s.is_synthetic
ORDER BY bookings DESC, s.supplier_id;
