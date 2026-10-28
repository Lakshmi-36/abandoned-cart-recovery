USE abandoned_cart_full_db;

-- 1. Total campaigns
SELECT COUNT(*) AS total_campaigns
FROM campaigns;

-- 2. Campaigns by channel
SELECT
    channel,
    COUNT(*) AS total_campaigns
FROM campaigns
GROUP BY channel;

-- 3. Campaigns by status
SELECT
    campaign_status,
    COUNT(*) AS total_campaigns
FROM campaigns
GROUP BY campaign_status;

-- 4. Total message templates
SELECT COUNT(*) AS total_templates
FROM message_templates;

-- 5. Total campaign-template mappings
SELECT COUNT(*) AS total_campaign_template_mappings
FROM campaign_templates;

-- 6. Campaigns without template mappings
SELECT COUNT(*) AS campaigns_without_templates
FROM campaigns c
WHERE NOT EXISTS (
    SELECT 1
    FROM campaign_templates ct
    WHERE ct.campaign_id = c.campaign_id
);

-- 7. Campaign-template mappings without a matching campaign
SELECT COUNT(*) AS orphan_campaign_mappings
FROM campaign_templates ct
LEFT JOIN campaigns c
    ON c.campaign_id = ct.campaign_id
WHERE c.campaign_id IS NULL;