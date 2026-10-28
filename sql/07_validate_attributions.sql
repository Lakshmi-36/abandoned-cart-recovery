USE abandoned_cart_full_db;

-- 1. Total attribution records
SELECT COUNT(*) AS total_attributions
FROM attributions;

-- 2. Attribution records by status
SELECT
    attribution_status,
    COUNT(*) AS total_records
FROM attributions
GROUP BY attribution_status;

-- 3. Attribution records by model
SELECT
    attribution_model,
    COUNT(*) AS total_records
FROM attributions
GROUP BY attribution_model;

-- 4. Attributions without matching orders
SELECT COUNT(*) AS orphan_attributions
FROM attributions a
LEFT JOIN orders o
    ON o.order_id = a.order_id
WHERE o.order_id IS NULL;

-- 5. Attributions without matching campaign enrollments
SELECT COUNT(*) AS orphan_campaign_attributions
FROM attributions a
LEFT JOIN campaign_carts cc
    ON cc.campaign_cart_id = a.campaign_cart_id
WHERE cc.campaign_cart_id IS NULL;

-- 6. Orders receiving duplicate credited attribution
SELECT COUNT(*) AS orders_with_duplicate_credit
FROM (
    SELECT order_id
    FROM attributions
    WHERE attribution_status = 'CREDITED'
    GROUP BY order_id
    HAVING COUNT(*) > 1
) duplicates;

-- 7. Check for credited attribution with non-positive revenue
SELECT COUNT(*) AS invalid_credited_revenue
FROM attributions
WHERE attribution_status = 'CREDITED'
  AND credited_revenue <= 0;

-- 8. Check attribution windows that are not positive
SELECT COUNT(*) AS invalid_attribution_windows
FROM attributions
WHERE attribution_window_hours <= 0;