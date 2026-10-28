USE abandoned_cart_full_db;

-- 1. MESSAGE_SENT_AFTER_OPTOUT
-- Find successful sends where the latest consent
-- event at send time was OPTED_OUT.

SELECT
    s.send_id,
    s.customer_id,
    s.channel,
    s.attempted_at,
    (
        SELECT ce.consent_status
        FROM consent_events ce
        WHERE ce.customer_id = s.customer_id
          AND ce.channel = s.channel
          AND ce.effective_at <= s.attempted_at
        ORDER BY
            ce.effective_at DESC,
            ce.consent_event_id DESC
        LIMIT 1
    ) AS consent_at_send
FROM send_attempts s
WHERE s.send_status = 'SENT'
  AND (
      SELECT ce.consent_status
      FROM consent_events ce
      WHERE ce.customer_id = s.customer_id
        AND ce.channel = s.channel
        AND ce.effective_at <= s.attempted_at
      ORDER BY
          ce.effective_at DESC,
          ce.consent_event_id DESC
      LIMIT 1
  ) = 'OPTED_OUT';


-- 2. CART_ABANDONED_AFTER_PURCHASE
-- Find carts marked abandoned after a purchase
-- linked to the same cart.

SELECT
    c.cart_id,
    c.abandoned_at,
    o.order_id,
    o.ordered_at
FROM carts c
JOIN orders o
    ON o.cart_id = c.cart_id
WHERE c.abandoned_at > o.ordered_at;


-- 3. DUPLICATE_CONVERSION_ATTRIBUTION
-- Find orders receiving more than one credited
-- attribution record.

SELECT
    order_id,
    COUNT(*) AS credited_records,
    SUM(credited_revenue) AS total_credited_revenue
FROM attributions
WHERE attribution_status = 'CREDITED'
GROUP BY order_id
HAVING COUNT(*) > 1;


-- 4. STALE_CART_TOTAL_AFTER_QUANTITY_UPDATE
-- Compare stored totals only against carts with active cart lines.

SELECT
    c.cart_id,
    c.cart_total AS stored_cart_total,
    t.calculated_total AS calculated_cart_total
FROM carts AS c
JOIN (
    SELECT
        cart_id,
        SUM(quantity * unit_price) AS calculated_total
    FROM cart_lines
    WHERE line_status = 'ACTIVE'
    GROUP BY cart_id
) AS t
    ON t.cart_id = c.cart_id
WHERE ABS(c.cart_total - t.calculated_total) > 0.01;