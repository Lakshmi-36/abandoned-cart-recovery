import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


# --------------------------------------------------
# 1. Project configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "project_config.json"

# Fixed snapshot time keeps the synthetic data reproducible.
SNAPSHOT_AT = datetime(2026, 10, 26, 0, 0, 0)

# Expanded synthetic product catalogue.
# Prices are illustrative INR values, not live retail prices.
PRODUCTS = [
    ("SKU-1001", "Cotton T-Shirt", 499.00),
    ("SKU-1002", "Denim Jeans", 1299.00),
    ("SKU-1003", "Running Shoes", 2499.00),
    ("SKU-1004", "Backpack", 899.00),
    ("SKU-1005", "Water Bottle", 299.00),
    ("SKU-1006", "Wireless Earbuds", 1799.00),
    ("SKU-1007", "Notebook Set", 199.00),
    ("SKU-1008", "Desk Lamp", 799.00),
    ("SKU-1009", "Phone Case", 349.00),
    ("SKU-1010", "Travel Mug", 449.00),
    ("SKU-1011", "Hoodie", 1199.00),
    ("SKU-1012", "Casual Shirt", 899.00),
    ("SKU-1013", "Leggings", 599.00),
    ("SKU-1014", "Sports Socks", 249.00),
    ("SKU-1015", "Baseball Cap", 399.00),
    ("SKU-1016", "Laptop Sleeve", 699.00),
    ("SKU-1017", "Wireless Mouse", 599.00),
    ("SKU-1018", "Mechanical Keyboard", 2299.00),
    ("SKU-1019", "Power Bank", 1299.00),
    ("SKU-1020", "USB-C Cable", 299.00),
    ("SKU-1021", "Bluetooth Speaker", 1499.00),
    ("SKU-1022", "Smartwatch Strap", 499.00),
    ("SKU-1023", "Sunglasses", 799.00),
    ("SKU-1024", "Wallet", 649.00),
    ("SKU-1025", "Handbag", 1599.00),
    ("SKU-1026", "Skincare Set", 999.00),
    ("SKU-1027", "Insulated Lunch Box", 549.00),
    ("SKU-1028", "Yoga Mat", 1099.00),
    ("SKU-1029", "Resistance Bands", 399.00),
    ("SKU-1030", "Cookware Set", 1999.00),
    ("SKU-1031", "Bedsheet Set", 1399.00),
    ("SKU-1032", "Pillow", 699.00),
    ("SKU-1033", "Storage Organizer", 449.00),
    ("SKU-1034", "LED Bulb Pack", 349.00),
    ("SKU-1035", "Coffee Beans", 599.00),
    ("SKU-1036", "Ceramic Mug", 299.00),
    ("SKU-1037", "Board Game", 1299.00),
    ("SKU-1038", "Paperback Novel", 399.00),
    ("SKU-1039", "Pet Food Pack", 799.00),
    ("SKU-1040", "Pet Toy", 349.00),
]


def load_config():
    """Load the project's JSON configuration."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def make_cart_id(number):
    """Create the required cart ID format."""
    return f"CART-2026-{number:06d}"


def random_datetime(rng, start, end):
    """Generate a reproducible datetime between two dates."""
    if end < start:
        raise ValueError(
            "The end datetime cannot precede the start."
        )

    seconds = int((end - start).total_seconds())

    return start + timedelta(
        seconds=rng.randint(0, seconds)
    )


def insert_in_batches(cursor, sql, records, batch_size=1000):
    """Insert records in manageable batches."""
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        cursor.executemany(sql, batch)
def generate_cart_data(mode):
    config = load_config()

    seed = config["project"]["random_seed"]
    settings = config["data_generation"][mode]

    target_carts = settings["target_carts"]
    target_abandoned = settings["target_abandoned_carts"]

    inactivity_hours = config["business_rules"][
        "abandonment_inactivity_hours"
    ]

    if target_carts <= 0:
        raise ValueError("Target carts must be greater than zero.")

    if not 0 <= target_abandoned <= target_carts:
        raise ValueError(
            "Abandoned-cart target must be between zero "
            "and total carts."
        )

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # ------------------------------------------
        # 2. Check master data
        # ------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]

        if customer_count < target_carts:
            raise ValueError(
                f"Need at least {target_carts:,} customers, "
                f"but only {customer_count:,} exist."
            )

        cursor.execute("""
            SELECT
                c.customer_id,
                s.session_id,
                s.started_at
            FROM customers c
            JOIN sessions s
                ON s.customer_id = c.customer_id
            ORDER BY c.customer_id
            LIMIT %s
        """, (target_carts,))

        master_records = cursor.fetchall()

        if len(master_records) < target_carts:
            raise ValueError(
                f"Need {target_carts:,} customers with matching "
                f"sessions, but found {len(master_records):,}."
            )

        # ------------------------------------------
        # 3. Identify existing carts
        # ------------------------------------------

        cursor.execute("""
            SELECT cart_id
            FROM carts
            WHERE cart_id LIKE 'CART-2026-%'
        """)

        existing_cart_ids = {
            row[0] for row in cursor.fetchall()
        }

        carts = []
        cart_lines = []
        cart_events = []

        abandoned_count = 0
        active_count = 0
        session_timeline_conflict_count = 0

        # ------------------------------------------
        # 4. Generate carts
        # ------------------------------------------

        for number, master in enumerate(master_records, start=1):

            customer_id, session_id, session_started_at = master

            cart_id = make_cart_id(number)

            # Never duplicate existing cart records.
            # Existing carts are left unchanged.
            if cart_id in existing_cart_ids:
                continue

            # A separate deterministic random generator per cart.
            rng = random.Random(seed + number)

            # Distribute abandoned carts throughout the dataset.
            is_abandoned = (
                number * target_abandoned // target_carts
                >
                (number - 1) * target_abandoned // target_carts
            )

            if is_abandoned:

                # Randomise inactivity to the second.
                # The cart becomes abandoned after the configured
                # inactivity threshold.
                min_inactive_seconds = (
                    inactivity_hours * 60 * 60 + 1
                )

                max_inactive_seconds = 10 * 24 * 60 * 60

                seconds_inactive = rng.randint(
                    min_inactive_seconds,
                    max_inactive_seconds,
                )

                last_activity_at = (
                    SNAPSHOT_AT
                    - timedelta(seconds=seconds_inactive)
                )

                abandoned_at = (
                    last_activity_at
                    + timedelta(hours=inactivity_hours)
                )

                cart_status = "ABANDONED"
                abandoned_count += 1

            else:

                # Active carts have activity within the last 23 hours.
                seconds_since_activity = rng.randint(
                    1,
                    23 * 60 * 60,
                )

                last_activity_at = (
                    SNAPSHOT_AT
                    - timedelta(seconds=seconds_since_activity)
                )

                abandoned_at = None
                cart_status = "ACTIVE"
                active_count += 1

            # --------------------------------------
            # 5. Create a consistent cart timeline
            # --------------------------------------

            proposed_creation = last_activity_at - timedelta(
                hours=rng.randint(1, 48)
            )

            earliest_valid_creation = max(
                proposed_creation,
                session_started_at,
            )

            timeline_conflict = (
                earliest_valid_creation > last_activity_at
            )

            if timeline_conflict:
                session_timeline_conflict_count += 1
                created_at = last_activity_at
            else:
                created_at = earliest_valid_creation

            updated_at = last_activity_at

            # --------------------------------------
            # 6. Generate product lines
            # --------------------------------------

            number_of_items = rng.randint(1, 5)

            selected_products = rng.sample(
                PRODUCTS,
                number_of_items,
            )

            cart_total = 0.0

            for sku, product_name, unit_price in selected_products:

                quantity = rng.randint(1, 3)

                added_at = random_datetime(
                    rng,
                    created_at,
                    last_activity_at,
                )

                updated_line_at = random_datetime(
                    rng,
                    added_at,
                    last_activity_at,
                )

                line_total = round(quantity * unit_price, 2)
                cart_total += line_total

                cart_lines.append((
                    cart_id,
                    sku,
                    product_name,
                    quantity,
                    unit_price,
                    added_at,
                    updated_line_at,
                    None,
                    "ACTIVE",
                ))

                cart_events.append((
                    cart_id,
                    "ITEM_ADDED",
                    added_at,
                    None,
                    None,
                    json.dumps({
                        "product_sku": sku,
                        "quantity": quantity,
                        "unit_price": unit_price,
                    }),
                ))

            cart_total = round(cart_total, 2)

            carts.append((
                cart_id,
                customer_id,
                session_id,
                "INR",
                cart_total,
                created_at,
                updated_at,
                last_activity_at,
                abandoned_at,
                None,
                None,
                cart_status,
            ))

            # A newly created cart starts as ACTIVE.
            cart_events.append((
                cart_id,
                "CREATED",
                created_at,
                None,
                "ACTIVE",
                json.dumps({
                    "source": "SYNTHETIC_GENERATOR",
                    "snapshot_at": SNAPSHOT_AT.isoformat(),
                    "session_timeline_conflict": timeline_conflict,
                }),
            ))

            # Abandonment is recorded as a separate event.
            if is_abandoned:
                cart_events.append((
                    cart_id,
                    "ABANDONED",
                    abandoned_at,
                    "ACTIVE",
                    "ABANDONED",
                    json.dumps({
                        "reason": "INACTIVITY_THRESHOLD_EXCEEDED",
                        "inactivity_hours": inactivity_hours,
                    }),
                ))
                        # ------------------------------------------
        # 7. Insert cart records
        # ------------------------------------------

        cart_sql = """
            INSERT INTO carts
            (
                cart_id,
                customer_id,
                session_id,
                currency,
                cart_total,
                created_at,
                updated_at,
                last_activity_at,
                abandoned_at,
                recovered_at,
                closed_at,
                cart_status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """

        insert_in_batches(cursor, cart_sql, carts)

        # ------------------------------------------
        # 8. Insert cart lines
        # ------------------------------------------

        line_sql = """
            INSERT INTO cart_lines
            (
                cart_id,
                product_sku,
                product_name,
                quantity,
                unit_price,
                added_at,
                updated_at,
                removed_at,
                line_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        insert_in_batches(cursor, line_sql, cart_lines)

        # ------------------------------------------
        # 9. Insert cart event history
        # ------------------------------------------

        event_sql = """
            INSERT INTO cart_events
            (
                cart_id,
                event_type,
                event_at,
                previous_status,
                new_status,
                event_details
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cart_events.sort(
            key=lambda event: (event[0], event[2])
        )

        insert_in_batches(cursor, event_sql, cart_events)

        connection.commit()

        # ------------------------------------------
        # 10. Report results
        # ------------------------------------------

        print("\nCart generation completed successfully.")
        print(f"Mode: {mode}")
        print(f"Random seed: {seed}")
        print(f"Snapshot time: {SNAPSHOT_AT}")
        print(f"Target carts: {target_carts:,}")
        print(f"New carts generated: {len(carts):,}")
        print(f"New abandoned carts generated: {abandoned_count:,}")
        print(f"New active carts generated: {active_count:,}")
        print(f"New cart lines generated: {len(cart_lines):,}")
        print(f"New cart events generated: {len(cart_events):,}")

        print(
            "Carts with session/cart timeline conflicts: "
            f"{session_timeline_conflict_count:,}"
        )

        print("\nActual database totals:")

        for table in ("carts", "cart_lines", "cart_events"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]:,}")

    except (Error, ValueError):
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
            "Generate deterministic cart data and cart event history."
        )
    )

    parser.add_argument(
        "mode",
        choices=["starter", "full"],
        nargs="?",
        default="starter",
        help="Choose starter or full dataset.",
    )

    args = parser.parse_args()

    try:
        generate_cart_data(args.mode)

    except (Error, OSError, ValueError, KeyError) as error:
        print(f"Cart generation failed: {error}")
        raise SystemExit(1)