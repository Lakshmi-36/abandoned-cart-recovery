-- ============================================================
-- ADDITIONAL READ-ONLY BUSINESS-RULE VALIDATION
-- Database: abandoned_cart_full_db
-- MySQL 8.4
--
-- This script contains SELECT statements only. It does not
-- modify data. Review the results before deciding on fixes.
-- Do not use it as a substitute for the original validation files.
-- ============================================================

USE abandoned_cart_full_db;

-- 1. ID format checks: each query should return zero rows.
SELECT customer_id
FROM customers
WHERE customer_id NOT REGEXP '^CUS-[0-9]{6}$';

SELECT cart_id
FROM carts
WHERE cart_id NOT REGEXP '^CART-2026-[0-9]{6}$';

SELECT campaign_id
FROM campaigns
WHERE campaign_id NOT REGEXP '^CMP-2026-[0-9]{6}$';

SELECT send_id
FROM send_attempts
WHERE send_id NOT REGEXP '^SEND-2026-[0-9]{6}$';

SELECT order_id
FROM orders
WHERE order_id NOT REGEXP '^ORD-2026-[0-9]{6}$';

-- 2. Required parent/child joins: each query should return zero.
SELECT c.cart_id
FROM carts c
LEFT JOIN customers cu ON cu.customer_id = c.customer_id
WHERE cu.customer_id IS NULL;

SELECT c.cart_id
FROM carts c
LEFT JOIN sessions s ON s.session_id = c.session_id
WHERE c.session_id IS NOT NULL AND s.session_id IS NULL;

SELECT cc.campaign_cart_id
FROM campaign_carts cc
LEFT JOIN campaigns c ON c.campaign_id = cc.campaign_id
LEFT JOIN carts ca ON ca.cart_id = cc.cart_id
WHERE c.campaign_id IS NULL OR ca.cart_id IS NULL;

SELECT a.attribution_id
FROM attributions a
LEFT JOIN orders o ON o.order_id = a.order_id
LEFT JOIN campaign_carts cc ON cc.campaign_cart_id = a.campaign_cart_id
WHERE o.order_id IS NULL OR cc.campaign_cart_id IS NULL;

-- 3. Abandonment timing: baseline abandoned carts should have
-- at least the configured 24 hours of inactivity at abandonment.
-- Review returned rows; do not automatically rewrite timestamps.
SELECT cart_id, last_activity_at, abandoned_at,
       TIMESTAMPDIFF(HOUR, last_activity_at, abandoned_at) AS inactive_hours
FROM carts
WHERE cart_status = 'ABANDONED'
  AND (
      abandoned_at IS NULL
      OR abandoned_at < DATE_ADD(last_activity_at, INTERVAL 24 HOUR)
  );

-- 4. Lifecycle consistency: review any returned rows.
SELECT cart_id, cart_status, abandoned_at, recovered_at, closed_at
FROM carts
WHERE (cart_status = 'ABANDONED' AND abandoned_at IS NULL)
   OR (cart_status = 'RECOVERED' AND recovered_at IS NULL)
   OR (cart_status = 'CLOSED' AND closed_at IS NULL)
   OR (recovered_at IS NOT NULL AND abandoned_at IS NOT NULL
       AND recovered_at < abandoned_at);

-- 5. Orders after a cart is marked abandoned: these can be legitimate
-- later purchases, so review them rather than treating every row as
-- an error. An abandonment timestamp AFTER the purchase is invalid.
SELECT c.cart_id, c.abandoned_at, o.order_id, o.ordered_at
FROM carts c
JOIN orders o ON o.cart_id = c.cart_id
WHERE c.abandoned_at > o.ordered_at;

-- 6. Cart arithmetic: compare stored totals against active cart lines.
-- Carts without active lines are excluded from this check.
-- Expected valid baseline result: zero rows.

SELECT
    c.cart_id,
    c.cart_total,
    x.calculated_total
FROM carts AS c
JOIN (
    SELECT
        cart_id,
        SUM(quantity * unit_price) AS calculated_total
    FROM cart_lines
    WHERE line_status = 'ACTIVE'
    GROUP BY cart_id
) AS x
    ON x.cart_id = c.cart_id
WHERE ABS(c.cart_total - x.calculated_total) > 0.01;

-- 7. Consent and frequency cap are evaluated at send time.
-- Successful sends without a valid latest opt-in should return zero rows.
SELECT s.send_id, s.customer_id, s.channel, s.attempted_at,
       (
         SELECT ce.consent_status
         FROM consent_events ce
         WHERE ce.customer_id = s.customer_id
           AND ce.channel = s.channel
           AND ce.effective_at <= s.attempted_at
         ORDER BY ce.effective_at DESC, ce.consent_event_id DESC
         LIMIT 1
       ) AS consent_at_send
FROM send_attempts s
WHERE s.send_status = 'SENT'
  AND COALESCE((
         SELECT ce.consent_status
         FROM consent_events ce
         WHERE ce.customer_id = s.customer_id
           AND ce.channel = s.channel
           AND ce.effective_at <= s.attempted_at
         ORDER BY ce.effective_at DESC, ce.consent_event_id DESC
         LIMIT 1
      ), 'UNKNOWN') <> 'OPTED_IN';

-- Fourth and subsequent successful sends in any rolling seven-day
-- window should be absent in valid baseline data.
SELECT s.send_id, s.customer_id, s.channel, s.attempted_at,
       (
         SELECT COUNT(*)
         FROM send_attempts p
         WHERE p.customer_id = s.customer_id
           AND p.channel = s.channel
           AND p.send_status = 'SENT'
           AND p.attempted_at > DATE_SUB(s.attempted_at, INTERVAL 7 DAY)
           AND p.attempted_at <= s.attempted_at
       ) AS sends_in_rolling_window
FROM send_attempts s
WHERE s.send_status = 'SENT'
  AND (
         SELECT COUNT(*)
         FROM send_attempts p
         WHERE p.customer_id = s.customer_id
           AND p.channel = s.channel
           AND p.send_status = 'SENT'
           AND p.attempted_at > DATE_SUB(s.attempted_at, INTERVAL 7 DAY)
           AND p.attempted_at <= s.attempted_at
      ) > 3;

-- 8. Campaign-template channel consistency: review any returned rows.
SELECT c.campaign_id, c.channel AS campaign_channel,
       t.template_id, t.channel AS template_channel
FROM campaigns c
JOIN campaign_templates ct ON ct.campaign_id = c.campaign_id
JOIN message_templates t ON t.template_id = ct.template_id
WHERE c.channel <> t.channel;

-- 9. Message-event chronology: an event must not occur before its send
-- attempt. Events after send time are not required to follow a fixed order
-- because provider events can arrive late; inspect event sequence separately.
SELECT me.message_event_id, me.send_id, me.event_type,
       s.attempted_at, me.event_at
FROM message_events me
JOIN send_attempts s ON s.send_id = me.send_id
WHERE me.event_at < s.attempted_at;

-- 10. Order arithmetic: valid baseline rows should reconcile.
SELECT o.order_id, o.order_total,
       COALESCE(x.calculated_total, 0.00) AS calculated_total
FROM orders o
LEFT JOIN (
    SELECT order_id, SUM(line_total) AS calculated_total
    FROM order_lines
    GROUP BY order_id
) x ON x.order_id = o.order_id
WHERE ABS(o.order_total - COALESCE(x.calculated_total, 0.00)) > 0.01;

-- 11. Attribution model/window sanity checks.
-- A valid credited attribution must be within its documented positive
-- window relative to the order. This check assumes attributed_at is the
-- timestamp when the attribution was recorded; confirm project semantics
-- before interpreting the timestamp difference as the click window.
SELECT a.attribution_id, a.order_id, a.attributed_at, o.ordered_at,
       a.attribution_window_hours,
       TIMESTAMPDIFF(HOUR, a.attributed_at, o.ordered_at) AS hours_to_order
FROM attributions a
JOIN orders o ON o.order_id = a.order_id
WHERE a.attribution_status = 'CREDITED'
  AND (
      a.attribution_window_hours <= 0
      OR o.ordered_at < a.attributed_at
      OR TIMESTAMPDIFF(HOUR, a.attributed_at, o.ordered_at)
            > a.attribution_window_hours
  );

-- 12. Revenue reconciliation: credited revenue must not exceed the
-- order's revenue due to duplicate credits. Each returned order needs review.
SELECT o.order_id, o.order_total,
       SUM(CASE WHEN a.attribution_status = 'CREDITED'
                THEN a.credited_revenue ELSE 0 END) AS total_credited_revenue,
       SUM(CASE WHEN a.attribution_status = 'CREDITED'
                THEN 1 ELSE 0 END) AS credited_rows
FROM orders o
JOIN attributions a ON a.order_id = o.order_id
GROUP BY o.order_id, o.order_total
HAVING credited_rows > 1
    OR ABS(total_credited_revenue - o.order_total) > 0.01;

-- 13. Row-count summary across all 16 project tables.
SELECT 'customers' AS table_name, COUNT(*) AS total_records FROM customers
UNION ALL SELECT 'consent_events', COUNT(*) FROM consent_events
UNION ALL SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL SELECT 'carts', COUNT(*) FROM carts
UNION ALL SELECT 'cart_lines', COUNT(*) FROM cart_lines
UNION ALL SELECT 'cart_events', COUNT(*) FROM cart_events
UNION ALL SELECT 'campaigns', COUNT(*) FROM campaigns
UNION ALL SELECT 'message_templates', COUNT(*) FROM message_templates
UNION ALL SELECT 'campaign_templates', COUNT(*) FROM campaign_templates
UNION ALL SELECT 'campaign_carts', COUNT(*) FROM campaign_carts
UNION ALL SELECT 'send_attempts', COUNT(*) FROM send_attempts
UNION ALL SELECT 'message_events', COUNT(*) FROM message_events
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_lines', COUNT(*) FROM order_lines
UNION ALL SELECT 'order_events', COUNT(*) FROM order_events
UNION ALL SELECT 'attributions', COUNT(*) FROM attributions
ORDER BY table_name;
