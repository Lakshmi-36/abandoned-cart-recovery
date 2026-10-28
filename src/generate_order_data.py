import argparse
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


# ============================================================
# 1. PROJECT SETTINGS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SNAPSHOT_AT = datetime(2026, 10, 26, 0, 0, 0)

# Keep enough time for the PAID event, which occurs two
# minutes after the order.
LATEST_ORDER_TIME = SNAPSHOT_AT - timedelta(minutes=3)

CURRENCY = "INR"

RECOVERY_PURCHASE_PROBABILITY = 0.75

MIN_RECOVERY_DELAY = timedelta(minutes=5)
MIN_NON_RECOVERY_DELAY = timedelta(hours=1)
MAX_ORDER_DELAY = timedelta(hours=48)


# ============================================================
# 2. LOAD PROJECT CONFIGURATION
# ============================================================

def load_config():
    """Load project settings from the JSON configuration."""

    config_path = PROJECT_ROOT / "config" / "project_config.json"

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# 3. DATABASE INSERT HELPER
# ============================================================

def insert_in_batches(cursor, sql, records, batch_size=500):
    """Insert records in manageable batches."""

    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        cursor.executemany(sql, batch)


# ============================================================
# 4. LOAD ABANDONED CARTS
# ============================================================

def load_abandoned_carts(cursor):
    """Load abandoned carts that have an abandonment timestamp."""

    cursor.execute("""
        SELECT
            cart_id,
            customer_id,
            cart_total,
            abandoned_at
        FROM carts
        WHERE cart_status = 'ABANDONED'
          AND abandoned_at IS NOT NULL
        ORDER BY cart_id
    """)

    return cursor.fetchall()


# ============================================================
# 5. LOAD SUCCESSFUL RECOVERY MESSAGES
# ============================================================

def load_sent_messages(cursor):
    """
    Load successfully sent recovery messages.

    Each message is associated with a cart so that an order
    can be generated after the recovery message was sent.
    """

    cursor.execute("""
        SELECT
            cc.cart_id,
            sa.customer_id,
            sa.channel,
            sa.attempted_at,
            sa.send_status
        FROM campaign_carts cc
        JOIN send_attempts sa
            ON sa.campaign_cart_id = cc.campaign_cart_id
        WHERE sa.send_status = 'SENT'
        ORDER BY sa.attempted_at
    """)

    messages_by_cart = {}

    for message in cursor.fetchall():
        cart_id = message[0]

        messages_by_cart.setdefault(cart_id, []).append(message)

    return messages_by_cart


# ============================================================
# 6. LOAD ACTIVE CART LINES
# ============================================================

def load_cart_lines(cursor):
    """
    Load active cart lines once.

    This avoids running a separate SQL query for every cart.
    """

    cursor.execute("""
        SELECT
            cart_id,
            product_sku,
            product_name,
            quantity,
            unit_price
        FROM cart_lines
        WHERE line_status = 'ACTIVE'
        ORDER BY cart_id, cart_line_id
    """)

    lines_by_cart = {}

    for row in cursor.fetchall():
        cart_id = row[0]

        product_line = (
            row[1],  # product_sku
            row[2],  # product_name
            row[3],  # quantity
            row[4],  # unit_price
        )

        lines_by_cart.setdefault(cart_id, []).append(product_line)

    return lines_by_cart


# ============================================================
# 7. CHECK WHETHER A CART CAN PRODUCE A VALID ORDER
# ============================================================

def get_order_paths(cart, cart_messages):
    """
    Determine which order-generation paths are possible.

    Recovery path:
        Order must occur at least five minutes after both
        cart abandonment and the recovery-message send.

    Non-recovery path:
        Order must occur at least one hour after abandonment.

    Every generated order must leave enough time for its
    PAID event before the dataset snapshot.
    """

    cart_id, customer_id, cart_total, abandoned_at = cart

    paths = []

    # --------------------------------------------------------
    # PATH A: PURCHASE AFTER A RECOVERY MESSAGE
    # --------------------------------------------------------

    for message in cart_messages:
        attempted_at = message[3]

        if attempted_at is None:
            continue

        earliest_order_time = max(
            abandoned_at + MIN_RECOVERY_DELAY,
            attempted_at + MIN_RECOVERY_DELAY,
        )

        latest_order_time = min(
            earliest_order_time + MAX_ORDER_DELAY,
            LATEST_ORDER_TIME,
        )

        if earliest_order_time <= latest_order_time:
            paths.append({
                "type": "RECOVERY",
                "message": message,
                "earliest": earliest_order_time,
                "latest": latest_order_time,
            })

    # --------------------------------------------------------
    # PATH B: PURCHASE WITHOUT A RECOVERY MESSAGE
    # --------------------------------------------------------

    earliest_order_time = (
        abandoned_at + MIN_NON_RECOVERY_DELAY
    )

    latest_order_time = min(
        earliest_order_time + MAX_ORDER_DELAY,
        LATEST_ORDER_TIME,
    )

    if earliest_order_time <= latest_order_time:
        paths.append({
            "type": "NON_RECOVERY",
            "message": None,
            "earliest": earliest_order_time,
            "latest": latest_order_time,
        })

    return paths


# ============================================================
# 8. GENERATE A VALID ORDER TIMESTAMP
# ============================================================

def generate_order_timestamp(rng, path):
    """
    Generate an order timestamp within the valid time window.

    The timestamp is selected at second-level precision.
    """

    earliest = path["earliest"]
    latest = path["latest"]

    available_seconds = int(
        (latest - earliest).total_seconds()
    )

    random_seconds = rng.randint(0, available_seconds)

    return earliest + timedelta(seconds=random_seconds)


# ============================================================
# 9. CALCULATE ORDER TOTAL FROM CART LINES
# ============================================================

def calculate_order_lines(cart_items):
    """
    Build order lines from the original cart lines.

    The order total is calculated from quantity multiplied
    by unit price, rather than trusting the cart total alone.
    """

    order_total = Decimal("0.00")
    current_order_lines = []

    for (
        product_sku,
        product_name,
        quantity,
        unit_price,
    ) in cart_items:

        if quantity is None or quantity <= 0:
            raise ValueError(
                f"Invalid quantity for product {product_sku}."
            )

        if unit_price is None or Decimal(str(unit_price)) < 0:
            raise ValueError(
                f"Invalid unit price for product {product_sku}."
            )

        line_total = (
            Decimal(str(unit_price)) * Decimal(quantity)
        ).quantize(Decimal("0.01"))

        order_total += line_total

        current_order_lines.append({
            "product_sku": product_sku,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": unit_price,
        })

    order_total = order_total.quantize(Decimal("0.01"))

    return order_total, current_order_lines


# ============================================================
# 10. FIND THE NEXT AVAILABLE ORDER NUMBER
# ============================================================

def get_next_order_number(cursor):
    """
    Find the next order number without reusing existing IDs.
    """

    cursor.execute("""
        SELECT order_id
        FROM orders
        WHERE order_id LIKE 'ORD-2026-%'
    """)

    existing_order_ids = [
        row[0] for row in cursor.fetchall()
    ]

    if not existing_order_ids:
        return 1

    existing_numbers = []

    for order_id in existing_order_ids:
        try:
            number = int(order_id.rsplit("-", 1)[1])
            existing_numbers.append(number)
        except (ValueError, IndexError):
            continue

    if not existing_numbers:
        return 1

    return max(existing_numbers) + 1


# ============================================================
# 11. GENERATE ORDER DATA
# ============================================================

def generate_order_data(mode):

    config = load_config()

    seed = config["project"]["random_seed"]
    rng = random.Random(seed + 5000)

    # Keep generation targets controlled by project_config.json.
    try:
        target_orders = int(config["data_generation"][mode]["target_orders"])
    except KeyError:
        # Backward-compatible fallback to the configured cart target
        # only if target_orders has not yet been added to this mode.
        target_orders = int(config["data_generation"][mode]["target_abandoned_carts"])
    if target_orders < 0:
        raise ValueError("Configured target_orders must be non-negative.")

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # ----------------------------------------------------
        # STEP A: LOAD EXISTING DATA
        # ----------------------------------------------------

        abandoned_carts = load_abandoned_carts(cursor)

        if not abandoned_carts:
            raise ValueError(
                "No abandoned carts found. "
                "Generate cart data before generating orders."
            )

        messages_by_cart = load_sent_messages(cursor)

        lines_by_cart = load_cart_lines(cursor)

        # ----------------------------------------------------
        # STEP B: IDENTIFY CARTS ALREADY PURCHASED
        # ----------------------------------------------------

        cursor.execute("""
            SELECT cart_id
            FROM orders
            WHERE cart_id IS NOT NULL
        """)

        purchased_cart_ids = {
            row[0] for row in cursor.fetchall()
        }

        # ----------------------------------------------------
        # STEP C: FILTER ELIGIBLE CARTS BEFORE SELECTION
        # ----------------------------------------------------

        eligible_carts = []

        skipped_existing_order = 0
        skipped_timestamp = 0
        skipped_empty_cart = 0

        paths_by_cart = {}

        for cart in abandoned_carts:

            cart_id = cart[0]

            # Do not create a second order for the same cart.
            if cart_id in purchased_cart_ids:
                skipped_existing_order += 1
                continue

            # An order needs active cart lines.
            cart_items = lines_by_cart.get(cart_id, [])

            if not cart_items:
                skipped_empty_cart += 1
                continue

            # Find valid ways to generate an order.
            cart_messages = messages_by_cart.get(cart_id, [])

            valid_paths = get_order_paths(
                cart,
                cart_messages,
            )

            # If neither path fits the snapshot, exclude the cart
            # before selecting the target number of carts.
            if not valid_paths:
                skipped_timestamp += 1
                continue

            eligible_carts.append(cart)

            paths_by_cart[cart_id] = valid_paths

        if not eligible_carts:
            raise ValueError(
                "No eligible carts remain. Check abandoned-cart "
                "timestamps, active cart lines, and the dataset "
                "snapshot."
            )

        # ----------------------------------------------------
        # STEP D: SELECT ONLY ELIGIBLE CARTS
        # ----------------------------------------------------

        rng.shuffle(eligible_carts)

        selected_carts = eligible_carts[:target_orders]

        # ----------------------------------------------------
        # STEP E: PREPARE OUTPUT RECORDS
        # ----------------------------------------------------

        orders = []
        order_lines = []
        order_events = []

        recovery_orders = 0
        non_recovery_orders = 0

        next_number = get_next_order_number(cursor)

        # ----------------------------------------------------
        # STEP F: GENERATE ORDERS
        # ----------------------------------------------------

        for cart in selected_carts:

            (
                cart_id,
                customer_id,
                cart_total,
                abandoned_at,
            ) = cart

            cart_items = lines_by_cart[cart_id]

            valid_paths = paths_by_cart[cart_id]

            # Prefer the recovery path with probability 75%
            # when both recovery and non-recovery paths exist.
            recovery_paths = [
                path for path in valid_paths
                if path["type"] == "RECOVERY"
            ]

            non_recovery_paths = [
                path for path in valid_paths
                if path["type"] == "NON_RECOVERY"
            ]

            if recovery_paths and non_recovery_paths:
                if rng.random() < RECOVERY_PURCHASE_PROBABILITY:
                    selected_path = rng.choice(recovery_paths)
                else:
                    selected_path = non_recovery_paths[0]

            elif recovery_paths:
                selected_path = rng.choice(recovery_paths)

            elif non_recovery_paths:
                selected_path = non_recovery_paths[0]

            else:
                # Defensive check; eligible carts should always
                # have at least one valid path.
                skipped_timestamp += 1
                continue

            # Generate an order timestamp within the valid window.
            order_time = generate_order_timestamp(
                rng,
                selected_path,
            )

            # Validate the timestamp before creating records.
            if order_time > LATEST_ORDER_TIME:
                raise ValueError(
                    f"Generated order for {cart_id} exceeds "
                    "the allowed dataset timestamp."
                )

            payment_time = order_time + timedelta(minutes=2)

            if payment_time >= SNAPSHOT_AT:
                raise ValueError(
                    f"Payment event for {cart_id} exceeds "
                    "the dataset snapshot."
                )

            # Calculate the order from the actual cart lines.
            order_total, current_order_lines = (
                calculate_order_lines(cart_items)
            )

            # Generate a new, non-duplicate order ID.
            order_number = next_number + len(orders)

            order_id = f"ORD-2026-{order_number:06d}"

            # ------------------------------------------------
            # ADD ORDER RECORD
            # ------------------------------------------------

            orders.append((
                order_id,
                customer_id,
                cart_id,
                order_total,
                CURRENCY,
                order_time,
                "PAID",
            ))

            # ------------------------------------------------
            # ADD ORDER LINES
            # ------------------------------------------------

            for item in current_order_lines:

                order_lines.append((
                    order_id,
                    item["product_sku"],
                    item["product_name"],
                    item["quantity"],
                    item["unit_price"],
                ))

            # ------------------------------------------------
            # ADD ORDER LIFECYCLE EVENTS
            # ------------------------------------------------

            order_events.append((
                order_id,
                "PLACED",
                order_time,
                json.dumps({
                    "source": "SYNTHETIC_GENERATOR",
                    "cart_id": cart_id,
                    "purchase_path": selected_path["type"],
                }),
            ))

            order_events.append((
                order_id,
                "PAID",
                payment_time,
                json.dumps({
                    "payment_status": "SUCCESS",
                    "payment_method": "SYNTHETIC",
                }),
            ))

            if selected_path["type"] == "RECOVERY":
                recovery_orders += 1
            else:
                non_recovery_orders += 1

        # ----------------------------------------------------
        # STEP G: VALIDATE GENERATED RECORDS
        # ----------------------------------------------------

        if not orders:
            raise ValueError(
                "No orders could be generated. "
                "Check the available eligible carts."
            )

        if len(orders) > target_orders:
            raise ValueError(
                "Generated order count exceeds the target."
            )

        # Each order must have two lifecycle events.
        if len(order_events) != len(orders) * 2:
            raise ValueError(
                "Order-event count does not match the expected "
                "two events per order."
            )

        # ----------------------------------------------------
        # STEP H: INSERT ORDERS
        # ----------------------------------------------------

        insert_in_batches(
            cursor,
            """
            INSERT INTO orders
            (
                order_id,
                customer_id,
                cart_id,
                order_total,
                currency,
                ordered_at,
                order_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            orders,
        )

        # ----------------------------------------------------
        # STEP I: INSERT ORDER LINES
        # ----------------------------------------------------

        insert_in_batches(
            cursor,
            """
            INSERT INTO order_lines
            (
                order_id,
                product_sku,
                product_name,
                quantity,
                unit_price
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            order_lines,
        )

        # ----------------------------------------------------
        # STEP J: INSERT ORDER EVENTS
        # ----------------------------------------------------

        insert_in_batches(
            cursor,
            """
            INSERT INTO order_events
            (
                order_id,
                event_type,
                event_at,
                event_details
            )
            VALUES (%s, %s, %s, %s)
            """,
            order_events,
        )

        # ----------------------------------------------------
        # STEP K: COMMIT ALL INSERTS TOGETHER
        # ----------------------------------------------------

        connection.commit()

        # ----------------------------------------------------
        # STEP L: DISPLAY RESULTS
        # ----------------------------------------------------

        print("\n" + "=" * 55)
        print("ORDER GENERATION COMPLETED")
        print("=" * 55)

        print(f"Mode: {mode}")
        print(f"Random seed: {seed}")
        print(f"Target orders: {target_orders:,}")
        print(f"Orders created: {len(orders):,}")
        print(f"Order lines created: {len(order_lines):,}")
        print(f"Order events created: {len(order_events):,}")

        print("\nPurchase path breakdown:")
        print(f"Recovery-message path: {recovery_orders:,}")
        print(f"Non-recovery path: {non_recovery_orders:,}")

        print("\nCarts excluded:")
        print(f"Already have orders: {skipped_existing_order:,}")
        print(f"Invalid timestamps: {skipped_timestamp:,}")
        print(f"No active cart lines: {skipped_empty_cart:,}")

        print("\nEligible carts available before selection:")
        print(f"{len(eligible_carts):,}")

        print("\nActual database totals:")

        for table in (
            "orders",
            "order_lines",
            "order_events",
        ):
            cursor.execute(
                f"SELECT COUNT(*) FROM {table}"
            )

            total = cursor.fetchone()[0]

            print(f"{table}: {total:,}")

        print("=" * 55)

    except (Error, ValueError):
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ============================================================
# 12. SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic orders, order lines, "
            "and order lifecycle events."
        )
    )

    parser.add_argument(
        "mode",
        choices=["starter", "full"],
        nargs="?",
        default="starter",
        help="Choose starter or full dataset mode.",
    )

    args = parser.parse_args()

    try:
        generate_order_data(args.mode)

    except (Error, OSError, ValueError, KeyError) as error:
        print(f"\nOrder generation failed: {error}")
        raise SystemExit(1)