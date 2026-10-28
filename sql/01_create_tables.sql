-- ============================================================
-- PROJECT: Abandoned Cart Recovery and Attribution Pipeline
-- DATABASE: abandoned_cart_db
-- TARGET: MySQL 8.4
-- ============================================================

CREATE DATABASE IF NOT EXISTS abandoned_cart_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE abandoned_cart_db;


-- ============================================================
-- 1. CUSTOMERS
-- Master table: one record per customer.
-- Example ID: CUS-000001
-- ============================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(254),
    phone VARCHAR(25),
    country_code CHAR(2),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,

    CONSTRAINT chk_customer_dates
        CHECK (updated_at >= created_at)
) ENGINE = InnoDB;


-- ============================================================
-- 2. CONSENT HISTORY
-- Records consent changes instead of overwriting old consent.
-- A separate record is maintained for each channel change.
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_events (
    consent_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,

    channel ENUM('EMAIL', 'SMS') NOT NULL,
    consent_status ENUM('OPTED_IN', 'OPTED_OUT') NOT NULL,

    effective_at DATETIME NOT NULL,
    recorded_at DATETIME NOT NULL,

    source VARCHAR(50) NOT NULL,
    reason VARCHAR(255),

    CONSTRAINT fk_consent_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT chk_consent_recorded_date
        CHECK (recorded_at >= effective_at),

    INDEX idx_consent_customer_channel_date
        (customer_id, channel, effective_at)
) ENGINE = InnoDB;


-- ============================================================
-- 3. SESSIONS
-- A customer may use multiple sessions or devices.
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(40) PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,

    device_type ENUM(
        'MOBILE', 'DESKTOP', 'TABLET', 'OTHER'
    ) NOT NULL,

    started_at DATETIME NOT NULL,
    last_activity_at DATETIME NOT NULL,
    ended_at DATETIME NULL,

    session_status ENUM(
        'ACTIVE', 'ENDED', 'EXPIRED'
    ) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT fk_session_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT chk_session_activity
        CHECK (last_activity_at >= started_at),

    CONSTRAINT chk_session_end
        CHECK (ended_at IS NULL OR ended_at >= started_at),

    INDEX idx_session_customer (customer_id),
    INDEX idx_session_activity (last_activity_at)
) ENGINE = InnoDB;


-- ============================================================
-- 4. CARTS
-- Example ID: CART-2026-000001
--
-- cart_total is stored so that the pipeline can reconcile it
-- against cart lines and detect a deliberately stale total.
-- ============================================================

CREATE TABLE IF NOT EXISTS carts (
    cart_id VARCHAR(30) PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,
    session_id VARCHAR(40),

    currency CHAR(3) NOT NULL DEFAULT 'INR',
    cart_total DECIMAL(14,2) NOT NULL DEFAULT 0.00,

    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    last_activity_at DATETIME NOT NULL,

    abandoned_at DATETIME NULL,
    recovered_at DATETIME NULL,
    closed_at DATETIME NULL,

    cart_status ENUM(
        'ACTIVE',
        'ABANDONED',
        'RECOVERED',
        'CONVERTED',
        'CLOSED',
        'EXPIRED'
    ) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT fk_cart_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT fk_cart_session
        FOREIGN KEY (session_id)
        REFERENCES sessions(session_id),

    CONSTRAINT chk_cart_total
        CHECK (cart_total >= 0),

    CONSTRAINT chk_cart_dates
        CHECK (
            updated_at >= created_at
            AND last_activity_at >= created_at
        ),

    INDEX idx_cart_customer (customer_id),
    INDEX idx_cart_status_activity (cart_status, last_activity_at),
    INDEX idx_cart_abandoned (abandoned_at)
) ENGINE = InnoDB;


-- ============================================================
-- 5. CART LINES
-- One cart can contain multiple products.
-- ============================================================

CREATE TABLE IF NOT EXISTS cart_lines (
    cart_line_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cart_id VARCHAR(30) NOT NULL,

    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,

    quantity INT NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,

    line_total DECIMAL(14,2)
        GENERATED ALWAYS AS (quantity * unit_price) STORED,

    added_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    removed_at DATETIME NULL,

    line_status ENUM(
        'ACTIVE', 'REMOVED'
    ) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT fk_cart_line_cart
        FOREIGN KEY (cart_id)
        REFERENCES carts(cart_id),

    CONSTRAINT chk_cart_line_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_cart_line_price
        CHECK (unit_price >= 0),

    CONSTRAINT chk_cart_line_dates
        CHECK (updated_at >= added_at),

    INDEX idx_cart_line_cart (cart_id),
    INDEX idx_cart_line_sku (product_sku)
) ENGINE = InnoDB;


-- ============================================================
-- 6. CART EVENT HISTORY
-- Stores state changes and activities without overwriting them.
-- ============================================================

CREATE TABLE IF NOT EXISTS cart_events (
    cart_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cart_id VARCHAR(30) NOT NULL,

    event_type ENUM(
        'CREATED',
        'ITEM_ADDED',
        'ITEM_UPDATED',
        'ITEM_REMOVED',
        'ACTIVITY',
        'ABANDONED',
        'RECOVERED',
        'PURCHASED',
        'CLOSED',
        'EXPIRED'
    ) NOT NULL,

    event_at DATETIME NOT NULL,
    previous_status VARCHAR(30),
    new_status VARCHAR(30),

    event_details JSON,

    CONSTRAINT fk_cart_event_cart
        FOREIGN KEY (cart_id)
        REFERENCES carts(cart_id),

    INDEX idx_cart_event_cart_time (cart_id, event_at),
    INDEX idx_cart_event_type_time (event_type, event_at)
) ENGINE = InnoDB;


-- ============================================================
-- 7. CAMPAIGNS
-- Example ID: CMP-2026-000001
-- ============================================================

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id VARCHAR(30) PRIMARY KEY,
    campaign_name VARCHAR(200) NOT NULL,

    channel ENUM('EMAIL', 'SMS') NOT NULL,

    campaign_variant VARCHAR(50) NOT NULL,
    objective VARCHAR(100),

    scheduled_at DATETIME NOT NULL,
    started_at DATETIME NULL,
    ended_at DATETIME NULL,

    attribution_window_hours INT NOT NULL DEFAULT 168,

    campaign_status ENUM(
        'DRAFT',
        'SCHEDULED',
        'ACTIVE',
        'PAUSED',
        'COMPLETED',
        'CANCELLED'
    ) NOT NULL DEFAULT 'DRAFT',

    CONSTRAINT chk_campaign_window
        CHECK (attribution_window_hours > 0),

    CONSTRAINT chk_campaign_dates
        CHECK (
            ended_at IS NULL
            OR started_at IS NULL
            OR ended_at >= started_at
        ),

    INDEX idx_campaign_schedule (scheduled_at, campaign_status)
) ENGINE = InnoDB;


-- ============================================================
-- 8. MESSAGE TEMPLATES
-- ============================================================

CREATE TABLE IF NOT EXISTS message_templates (
    template_id VARCHAR(40) PRIMARY KEY,

    template_name VARCHAR(150) NOT NULL,
    channel ENUM('EMAIL', 'SMS') NOT NULL,

    subject VARCHAR(255),
    message_body TEXT NOT NULL,

    language_code VARCHAR(10) NOT NULL DEFAULT 'en',
    template_version INT NOT NULL DEFAULT 1,

    created_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_template_version
        CHECK (template_version > 0)
) ENGINE = InnoDB;


-- ============================================================
-- 9. CAMPAIGN-TEMPLATE BRIDGE
-- Supports multiple templates or variants per campaign.
-- This is a many-to-many relationship.
-- ============================================================

CREATE TABLE IF NOT EXISTS campaign_templates (
    campaign_id VARCHAR(30) NOT NULL,
    template_id VARCHAR(40) NOT NULL,

    variant_name VARCHAR(50) NOT NULL,
    allocation_percent DECIMAL(5,2) NOT NULL DEFAULT 100.00,

    PRIMARY KEY (campaign_id, template_id),

    CONSTRAINT fk_ct_campaign
        FOREIGN KEY (campaign_id)
        REFERENCES campaigns(campaign_id),

    CONSTRAINT fk_ct_template
        FOREIGN KEY (template_id)
        REFERENCES message_templates(template_id),

    CONSTRAINT chk_ct_allocation
        CHECK (
            allocation_percent > 0
            AND allocation_percent <= 100
        )
) ENGINE = InnoDB;


-- ============================================================
-- 10. CAMPAIGN-CART BRIDGE
-- Records which campaigns target which carts.
-- A cart may be associated with multiple campaigns.
-- ============================================================

CREATE TABLE IF NOT EXISTS campaign_carts (
    campaign_cart_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    campaign_id VARCHAR(30) NOT NULL,
    cart_id VARCHAR(30) NOT NULL,
    message_id VARCHAR(60),



    selected_template_id VARCHAR(40),
    enrolled_at DATETIME NOT NULL,

    eligibility_status ENUM(
        'ELIGIBLE',
        'SUPPRESSED',
        'PENDING',
        'COMPLETED'
    ) NOT NULL DEFAULT 'PENDING',

    suppression_reason VARCHAR(255),

    CONSTRAINT fk_cc_campaign
        FOREIGN KEY (campaign_id)
        REFERENCES campaigns(campaign_id),

    CONSTRAINT fk_cc_cart
        FOREIGN KEY (cart_id)
        REFERENCES carts(cart_id),

    CONSTRAINT fk_cc_template
        FOREIGN KEY (selected_template_id)
        REFERENCES message_templates(template_id),

    UNIQUE KEY uq_campaign_cart (campaign_id, cart_id),
    UNIQUE KEY uq_campaign_cart_message_id (message_id),


    INDEX idx_cc_cart (cart_id),
    INDEX idx_cc_eligibility (eligibility_status)
) ENGINE = InnoDB;


-- ============================================================
-- 11. SEND ATTEMPTS
-- Example ID: SEND-2026-000001
-- Records attempted sends, including suppressed attempts.
-- ============================================================

CREATE TABLE IF NOT EXISTS send_attempts (
    send_id VARCHAR(30) PRIMARY KEY,

    campaign_cart_id BIGINT NOT NULL,
    customer_id VARCHAR(20) NOT NULL,

    channel ENUM('EMAIL', 'SMS') NOT NULL,
    recipient VARCHAR(254) NOT NULL,

    attempted_at DATETIME NOT NULL,

    send_status ENUM(
        'PENDING',
        'SENT',
        'FAILED',
        'SUPPRESSED'
    ) NOT NULL,

    suppression_reason VARCHAR(255),
    provider_message_id VARCHAR(150),

    CONSTRAINT fk_send_campaign_cart
        FOREIGN KEY (campaign_cart_id)
        REFERENCES campaign_carts(campaign_cart_id),

    CONSTRAINT fk_send_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    INDEX idx_send_customer_channel_time
        (customer_id, channel, attempted_at),

    INDEX idx_send_campaign_cart (campaign_cart_id),
    INDEX idx_send_status (send_status)
) ENGINE = InnoDB;


-- ============================================================
-- 12. MESSAGE EVENT HISTORY
-- Tracks sending, delivery, opening, clicking, and failures.
-- ============================================================

CREATE TABLE IF NOT EXISTS message_events (
    message_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    send_id VARCHAR(30) NOT NULL,

    event_type ENUM(
        'QUEUED',
        'SENT',
        'DELIVERED',
        'BOUNCED',
        'OPENED',
        'CLICKED',
        'UNSUBSCRIBED',
        'FAILED'
    ) NOT NULL,

    event_at DATETIME NOT NULL,
    provider_event_id VARCHAR(150),
    event_details JSON,

    CONSTRAINT fk_message_event_send
        FOREIGN KEY (send_id)
        REFERENCES send_attempts(send_id),

    UNIQUE KEY uq_provider_event (provider_event_id),

    INDEX idx_message_event_send_time (send_id, event_at),
    INDEX idx_message_event_type_time (event_type, event_at)
) ENGINE = InnoDB;


-- ============================================================
-- 13. ORDERS
-- Example ID: ORD-2026-000001
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(30) PRIMARY KEY,

    customer_id VARCHAR(20) NOT NULL,
    cart_id VARCHAR(30),

    order_total DECIMAL(14,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'INR',

    ordered_at DATETIME NOT NULL,

    order_status ENUM(
        'PLACED',
        'PAID',
        'CANCELLED',
        'REFUNDED'
    ) NOT NULL DEFAULT 'PLACED',

    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT fk_order_cart
        FOREIGN KEY (cart_id)
        REFERENCES carts(cart_id),

    CONSTRAINT chk_order_total
        CHECK (order_total >= 0),

    INDEX idx_order_customer_time (customer_id, ordered_at),
    INDEX idx_order_cart (cart_id),
    INDEX idx_order_status (order_status)
) ENGINE = InnoDB;


-- ============================================================
-- 14. ORDER LINES
-- Stores the products purchased.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_lines (
    order_line_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    order_id VARCHAR(30) NOT NULL,
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,

    quantity INT NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,

    line_total DECIMAL(14,2)
        GENERATED ALWAYS AS (quantity * unit_price) STORED,

    CONSTRAINT fk_order_line_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    CONSTRAINT chk_order_line_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_order_line_price
        CHECK (unit_price >= 0),

    INDEX idx_order_line_order (order_id)
) ENGINE = InnoDB;


-- ============================================================
-- 15. ORDER EVENT HISTORY
-- Preserves order lifecycle changes.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_events (
    order_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    order_id VARCHAR(30) NOT NULL,

    event_type ENUM(
        'PLACED',
        'PAID',
        'CANCELLED',
        'REFUNDED'
    ) NOT NULL,

    event_at DATETIME NOT NULL,
    event_details JSON,

    CONSTRAINT fk_order_event_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    INDEX idx_order_event_order_time (order_id, event_at)
) ENGINE = InnoDB;


-- ============================================================
-- 16. CONVERSION ATTRIBUTION
-- Records which campaign is credited for an order.
--
-- Multiple campaign claims for one order can be represented
-- and detected by validation. We intentionally do not enforce
-- one row per order at the database level because the project
-- must also test a double-attribution anomaly.
-- ============================================================

CREATE TABLE IF NOT EXISTS attributions (
    attribution_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    order_id VARCHAR(30) NOT NULL,
    campaign_cart_id BIGINT NOT NULL,

    attribution_model ENUM(
        'LAST_CLICK',
        'LAST_TOUCH',
        'FIRST_TOUCH'
    ) NOT NULL DEFAULT 'LAST_CLICK',

    attributed_at DATETIME NOT NULL,
    attribution_window_hours INT NOT NULL,

    credited_revenue DECIMAL(14,2) NOT NULL,

    attribution_status ENUM(
        'CANDIDATE',
        'CREDITED',
        'REJECTED'
    ) NOT NULL DEFAULT 'CANDIDATE',

    CONSTRAINT fk_attribution_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    CONSTRAINT fk_attribution_campaign_cart
        FOREIGN KEY (campaign_cart_id)
        REFERENCES campaign_carts(campaign_cart_id),

    CONSTRAINT chk_attribution_window
        CHECK (attribution_window_hours > 0),

    CONSTRAINT chk_attribution_revenue
        CHECK (credited_revenue >= 0),

    INDEX idx_attribution_order (order_id),
    INDEX idx_attribution_campaign_cart (campaign_cart_id),
    INDEX idx_attribution_status (attribution_status)
) ENGINE = InnoDB;


-- ============================================================
-- 17. VERIFY THE SCHEMA
-- ============================================================

SELECT DATABASE() AS active_database;

SHOW TABLES;