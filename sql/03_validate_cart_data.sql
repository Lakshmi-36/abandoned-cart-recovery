USE abandoned_cart_full_db;

-- 1. Total carts
SELECT COUNT(*) AS total_carts
FROM carts;

-- 2. Cart counts by status
SELECT
    cart_status,
    COUNT(*) AS total_carts
FROM carts
GROUP BY cart_status
ORDER BY cart_status;

-- 3. Compare cart totals with active cart lines
SELECT
    COUNT(*) AS total_carts,
    SUM(
        CASE
            WHEN ABS(
                c.cart_total -
                COALESCE(t.calculated_total, 0)
            ) > 0.01
            THEN 1
            ELSE 0
        END
    ) AS carts_with_total_mismatch
FROM carts c
LEFT JOIN (
    SELECT
        cart_id,
        SUM(line_total) AS calculated_total
    FROM cart_lines
    WHERE line_status = 'ACTIVE'
    GROUP BY cart_id
) t
    ON c.cart_id = t.cart_id;

-- 4. Check carts without any active lines
SELECT COUNT(*) AS carts_without_active_lines
FROM carts c
WHERE NOT EXISTS (
    SELECT 1
    FROM cart_lines cl
    WHERE cl.cart_id = c.cart_id
      AND cl.line_status = 'ACTIVE'
);

-- 5. Check abandoned carts without abandonment timestamps
SELECT COUNT(*) AS invalid_abandoned_carts
FROM carts
WHERE cart_status = 'ABANDONED'
  AND abandoned_at IS NULL;