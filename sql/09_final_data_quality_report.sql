USE abandoned_cart_full_db;

-- 1. Customer count
SELECT 'customers' AS table_name, COUNT(*) AS total_records
FROM customers

UNION ALL

-- 2. Session count
SELECT 'sessions', COUNT(*)
FROM sessions

UNION ALL

-- 3. Consent event count
SELECT 'consent_events', COUNT(*)
FROM consent_events

UNION ALL

-- 4. Cart count
SELECT 'carts', COUNT(*)
FROM carts

UNION ALL

-- 5. Cart-line count
SELECT 'cart_lines', COUNT(*)
FROM cart_lines

UNION ALL

-- 6. Campaign count
SELECT 'campaigns', COUNT(*)
FROM campaigns

UNION ALL

-- 7. Campaign enrollment count
SELECT 'campaign_carts', COUNT(*)
FROM campaign_carts

UNION ALL

-- 8. Send attempt count
SELECT 'send_attempts', COUNT(*)
FROM send_attempts

UNION ALL

-- 9. Message event count
SELECT 'message_events', COUNT(*)
FROM message_events

UNION ALL

-- 10. Order count
SELECT 'orders', COUNT(*)
FROM orders

UNION ALL

-- 11. Order-line count
SELECT 'order_lines', COUNT(*)
FROM order_lines

UNION ALL

-- 12. Order-event count
SELECT 'order_events', COUNT(*)
FROM order_events

UNION ALL

-- 13. Attribution count
SELECT 'attributions', COUNT(*)
FROM attributions

ORDER BY table_name;