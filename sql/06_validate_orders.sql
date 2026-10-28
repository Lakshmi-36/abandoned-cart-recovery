USE abandoned_cart_full_db;

-- 1. Total orders
SELECT COUNT(*) AS total_orders
FROM orders;

-- 2. Orders by status
SELECT
    order_status,
    COUNT(*) AS total_orders
FROM orders
GROUP BY order_status;

-- 3. Total order lines
SELECT COUNT(*) AS total_order_lines
FROM order_lines;

-- 4. Total order events
SELECT COUNT(*) AS total_order_events
FROM order_events;

-- 5. Orders without matching customers
SELECT COUNT(*) AS orders_without_customer
FROM orders o
LEFT JOIN customers c
    ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

-- 6. Order lines without matching orders
SELECT COUNT(*) AS orphan_order_lines
FROM order_lines ol
LEFT JOIN orders o
    ON o.order_id = ol.order_id
WHERE o.order_id IS NULL;

-- 7. Orders without any order lines
SELECT COUNT(*) AS orders_without_lines
FROM orders o
WHERE NOT EXISTS (
    SELECT 1
    FROM order_lines ol
    WHERE ol.order_id = o.order_id
);

-- 8. Compare order totals with order-line totals
SELECT
    COUNT(*) AS total_orders,
    SUM(
        CASE
            WHEN ABS(
                o.order_total -
                COALESCE(ol.calculated_total, 0)
            ) > 0.01
            THEN 1
            ELSE 0
        END
    ) AS orders_with_total_mismatch
FROM orders o
LEFT JOIN (
    SELECT
        order_id,
        SUM(line_total) AS calculated_total
    FROM order_lines
    GROUP BY order_id
) ol
    ON ol.order_id = o.order_id;

-- 9. Orders with events occurring before the order
SELECT COUNT(*) AS events_before_order
FROM order_events oe
JOIN orders o
    ON o.order_id = oe.order_id
WHERE oe.event_at < o.ordered_at;