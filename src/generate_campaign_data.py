import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "project_config.json"

SNAPSHOT_AT = datetime(2026, 10, 26, 0, 0, 0)

SCHEDULED_AT = datetime(2026, 10, 15, 23, 55, 0)
STARTED_AT = datetime(2026, 10, 16, 0, 0, 0)
ENDED_AT = SNAPSHOT_AT

TEMPLATE_ALLOCATION_PERCENT = 50.00

TEMPLATES = [
    (
        "TPL-EMAIL-001",
        "Email Cart Reminder",
        "EMAIL",
        "You left something in your cart!",
        "Hi {{first_name}}, your cart is waiting for you. "
        "Come back and complete your purchase.",
        "en",
        1,
        1,
    ),
    (
        "TPL-EMAIL-002",
        "Email Product Reminder",
        "EMAIL",
        "Still thinking it over?",
        "Hi {{first_name}}, the items you selected are waiting "
        "for you. Visit your cart to continue shopping.",
        "en",
        1,
        1,
    ),
    (
        "TPL-SMS-001",
        "SMS Cart Reminder",
        "SMS",
        None,
        "Your shopping cart is waiting! Return to the store "
        "to complete your purchase.",
        "en",
        1,
        1,
    ),
    (
        "TPL-SMS-002",
        "SMS Shopping Reminder",
        "SMS",
        None,
        "Still interested in your items? Your cart is ready "
        "when you are.",
        "en",
        1,
        1,
    ),
]


def load_config():
    """Load and validate the project configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_PATH}"
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    required_sections = [
        "project",
        "data_generation",
        "business_rules",
    ]

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"Missing configuration section: {section}"
            )

    return config


def validate_config(config, mode):
    """Validate the campaign-generation settings."""

    if mode not in config["data_generation"]:
        raise ValueError(
            f"Missing data-generation configuration for mode: {mode}"
        )

    mode_config = config["data_generation"][mode]

    if "target_campaigns" not in mode_config:
        raise ValueError(
            f"Missing target_campaigns for mode: {mode}"
        )

    target_campaigns = mode_config["target_campaigns"]

    if (
        not isinstance(target_campaigns, int)
        or isinstance(target_campaigns, bool)
        or target_campaigns <= 0
    ):
        raise ValueError(
            "target_campaigns must be a positive integer."
        )

    if "attribution_window_hours" not in config["business_rules"]:
        raise ValueError(
            "Missing business_rules.attribution_window_hours."
        )

    attribution_window_hours = (
        config["business_rules"]["attribution_window_hours"]
    )

    if (
        not isinstance(attribution_window_hours, int)
        or isinstance(attribution_window_hours, bool)
        or attribution_window_hours <= 0
    ):
        raise ValueError(
            "attribution_window_hours must be a positive integer."
        )

    if not (
        SCHEDULED_AT <= STARTED_AT < ENDED_AT <= SNAPSHOT_AT
    ):
        raise ValueError(
            "Invalid campaign timeline. Expected "
            "scheduled_at <= started_at < ended_at <= snapshot_at."
        )

    return target_campaigns, attribution_window_hours


def insert_in_batches(cursor, sql, records, batch_size=1000):
    """Insert records in batches."""

    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        cursor.executemany(sql, batch)


def build_template_records():
    """Build message-template records."""

    created_at = SNAPSHOT_AT - timedelta(days=60)

    return [
        (
            template_id,
            name,
            channel,
            subject,
            body,
            language,
            version,
            created_at,
            active,
        )
        for (
            template_id,
            name,
            channel,
            subject,
            body,
            language,
            version,
            active,
        ) in TEMPLATES
    ]


def build_campaign_records(target_campaigns, attribution_window_hours):
    """Build campaign records with consistent dates."""

    records = []

    for number in range(1, target_campaigns + 1):
        campaign_id = f"CMP-2026-{number:06d}"

        # Alternate email and SMS campaigns.
        channel = "EMAIL" if number % 2 == 1 else "SMS"

        # Assign campaign variants deterministically.
        variant = (
            "CART_REMINDER"
            if number % 4 in (1, 2)
            else "PRODUCT_REMINDER"
        )

        records.append(
            (
                campaign_id,
                f"Abandoned Cart Recovery {number:06d}",
                channel,
                variant,
                "Recover abandoned shopping carts",
                SCHEDULED_AT,
                STARTED_AT,
                ENDED_AT,
                attribution_window_hours,
                "COMPLETED",
            )
        )

    return records


def build_campaign_template_records(target_campaigns):
    """Map each campaign to its two channel-appropriate templates."""

    records = []

    for number in range(1, target_campaigns + 1):
        campaign_id = f"CMP-2026-{number:06d}"

        channel = "EMAIL" if number % 2 == 1 else "SMS"

        if channel == "EMAIL":
            template_ids = [
                "TPL-EMAIL-001",
                "TPL-EMAIL-002",
            ]
        else:
            template_ids = [
                "TPL-SMS-001",
                "TPL-SMS-002",
            ]

        for template_id in template_ids:
            variant_name = (
                "VARIANT_A"
                if template_id.endswith("001")
                else "VARIANT_B"
            )

            records.append(
                (
                    campaign_id,
                    template_id,
                    variant_name,
                    TEMPLATE_ALLOCATION_PERCENT,
                )
            )

    return records


def validate_campaign_template_records(records):
    """Check that every campaign's template allocations total 100%."""

    allocations = {}

    for campaign_id, template_id, variant_name, percentage in records:
        if percentage < 0 or percentage > 100:
            raise ValueError(
                f"Invalid allocation for campaign {campaign_id}: "
                f"{percentage}%"
            )

        allocations[campaign_id] = (
            allocations.get(campaign_id, 0) + percentage
        )

    invalid_campaigns = {
        campaign_id: total
        for campaign_id, total in allocations.items()
        if abs(total - 100.0) > 0.0001
    }

    if invalid_campaigns:
        raise ValueError(
            "Template allocations must total 100% per campaign. "
            f"Invalid allocations: {invalid_campaigns}"
        )


def print_table_totals(cursor):
    """Display current database totals."""

    print("\nActual database totals:")

    for table in (
        "message_templates",
        "campaigns",
        "campaign_templates",
    ):
        # Table names are fixed constants defined in this script.
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]

        print(f"{table}: {total:,}")


def generate_campaign_data(mode):
    """Generate campaign, template, and mapping records."""

    config = load_config()

    target_campaigns, attribution_window_hours = validate_config(
        config,
        mode,
    )

    template_records = build_template_records()

    campaign_records = build_campaign_records(
        target_campaigns,
        attribution_window_hours,
    )

    mapping_records = build_campaign_template_records(
        target_campaigns
    )

    validate_campaign_template_records(mapping_records)

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # 1. Insert message templates.
        template_sql = """
            INSERT IGNORE INTO message_templates
            (
                template_id,
                template_name,
                channel,
                subject,
                message_body,
                language_code,
                template_version,
                created_at,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        insert_in_batches(
            cursor,
            template_sql,
            template_records,
        )

        # 2. Insert campaigns.
        campaign_sql = """
            INSERT IGNORE INTO campaigns
            (
                campaign_id,
                campaign_name,
                channel,
                campaign_variant,
                objective,
                scheduled_at,
                started_at,
                ended_at,
                attribution_window_hours,
                campaign_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        insert_in_batches(
            cursor,
            campaign_sql,
            campaign_records,
        )

        # 3. Map campaigns to channel-appropriate templates.
        mapping_sql = """
            INSERT IGNORE INTO campaign_templates
            (
                campaign_id,
                template_id,
                variant_name,
                allocation_percent
            )
            VALUES (%s, %s, %s, %s)
        """

        insert_in_batches(
            cursor,
            mapping_sql,
            mapping_records,
        )

        # Commit all three stages together.
        connection.commit()

        print("\nCampaign generation completed successfully.")
        print(f"Mode: {mode}")
        print(f"Target campaigns requested: {target_campaigns:,}")
        print(f"Template definitions: {len(template_records):,}")
        print(f"Campaign records requested: {len(campaign_records):,}")
        print(f"Template mappings requested: {len(mapping_records):,}")
        print(
            "Attribution window: "
            f"{attribution_window_hours} hours"
        )
        print(
            "Template allocation per campaign: "
            "50% Variant A / 50% Variant B"
        )
        print(
            "Campaign window: "
            f"{STARTED_AT} to {ENDED_AT} (end exclusive)"
        )

        print_table_totals(cursor)

        print(
            "\nNote: INSERT IGNORE preserves existing records with "
            "conflicting unique keys. Database totals include records "
            "that existed before this run."
        )

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate campaigns, message templates, "
            "and campaign-template mappings."
        )
    )

    parser.add_argument(
        "mode",
        choices=["starter", "full"],
        nargs="?",
        default="starter",
        help="Data-generation mode (default: starter).",
    )

    args = parser.parse_args()

    try:
        generate_campaign_data(args.mode)

    except (
        Error,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
    ) as error:
        print(f"Campaign generation failed: {error}")
        raise SystemExit(1)