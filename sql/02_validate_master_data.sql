USE abandoned_cart_full_db;

-- 1. Total customers
SELECT COUNT(*) AS total_customers
FROM customers;

-- 2. Total sessions
SELECT COUNT(*) AS total_sessions
FROM sessions;

-- 3. Consent events by channel and status
SELECT
    channel,
    consent_status,
    COUNT(*) AS total_events
FROM consent_events
GROUP BY channel, consent_status
ORDER BY channel, consent_status;

-- 4. Check for duplicate customer IDs
SELECT
    customer_id,
    COUNT(*) AS duplicate_count
FROM customers
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- 5. Check sessions without a matching customer
SELECT COUNT(*) AS orphan_sessions
FROM sessions s
LEFT JOIN customers c
    ON s.customer_id = c.customer_id
WHERE c.customer_id IS NULL;