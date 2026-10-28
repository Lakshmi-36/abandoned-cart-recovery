USE abandoned_cart_full_db;

-- 1. Campaign-cart enrollments
SELECT
    eligibility_status,
    COUNT(*) AS total_enrollments
FROM campaign_carts
GROUP BY eligibility_status;

-- 2. Send attempts by status
SELECT
    send_status,
    COUNT(*) AS total_send_attempts
FROM send_attempts
GROUP BY send_status;

-- 3. Message events by type
SELECT
    event_type,
    COUNT(*) AS total_events
FROM message_events
GROUP BY event_type;

-- 4. Sends without matching enrollments
SELECT COUNT(*) AS unlinked_sends
FROM send_attempts s
LEFT JOIN campaign_carts cc
    ON s.campaign_cart_id = cc.campaign_cart_id
WHERE cc.campaign_cart_id IS NULL;

-- 5. Sends without a matching customer
SELECT COUNT(*) AS sends_without_customer
FROM send_attempts s
LEFT JOIN customers c
    ON s.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- 6. Successful sends without an earlier or
-- simultaneous opt-in as the latest consent event
SELECT COUNT(*) AS consent_violations
FROM send_attempts s
WHERE s.send_status = 'SENT'
  AND COALESCE(
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
      ),
      'UNKNOWN'
  ) <> 'OPTED_IN';

-- 7. Frequency-cap violations:
-- More than 3 successful sends to the same
-- customer and channel in any rolling 7-day window
SELECT COUNT(*) AS frequency_cap_violations
FROM send_attempts s
WHERE s.send_status = 'SENT'
  AND (
      SELECT COUNT(*)
      FROM send_attempts previous
      WHERE previous.customer_id = s.customer_id
        AND previous.channel = s.channel
        AND previous.send_status = 'SENT'
        AND previous.attempted_at > DATE_SUB(
            s.attempted_at,
            INTERVAL 7 DAY
        )
        AND previous.attempted_at <= s.attempted_at
  ) > 3;

-- 8. Message events without matching send attempts
SELECT COUNT(*) AS orphan_message_events
FROM message_events me
LEFT JOIN send_attempts s
    ON s.send_id = me.send_id
WHERE s.send_id IS NULL;