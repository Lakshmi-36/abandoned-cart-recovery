import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


# --------------------------------------------------
# 1. PROJECT SETTINGS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ATTRIBUTION_MODEL = "LAST_CLICK"
ATTRIBUTION_WINDOW_HOURS = 168

SNAPSHOT_AT = __import__("datetime").datetime(
    2026, 10, 26, 0, 0, 0
)


# --------------------------------------------------
# 2. LOAD PROJECT CONFIGURATION
# --------------------------------------------------

def load_config():
    """Load the project's configuration."""

    config_path = (
        PROJECT_ROOT
        / "config"
        / "project_config.json"
    )

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# 3. GENERATE ATTRIBUTIONS
# --------------------------------------------------

def generate_attributions():

    config = load_config()

    window_hours = config["business_rules"][
        "attribution_window_hours"
    ]

    if window_hours != ATTRIBUTION_WINDOW_HOURS:
        raise ValueError(
            "The configured attribution window does not match "
            "the expected 168-hour LAST_CLICK rule."
        )

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # ------------------------------------------
        # STEP A: FIND ELIGIBLE CLICK-TO-PURCHASE
        # MATCHES
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                o.order_id,
                o.cart_id,
                o.ordered_at,
                o.order_total,
                cc.campaign_cart_id,
                cc.campaign_id,
                sa.send_id,
                me.event_at AS click_at
            FROM orders o
            JOIN campaign_carts cc
                ON o.cart_id = cc.cart_id
            JOIN send_attempts sa
                ON sa.campaign_cart_id =
                   cc.campaign_cart_id
            JOIN message_events me
                ON me.send_id = sa.send_id
            WHERE sa.send_status = 'SENT'
              AND me.event_type = 'CLICKED'
              AND me.event_at >= sa.attempted_at
              AND me.event_at < o.ordered_at
              AND me.event_at >= DATE_SUB(
                  o.ordered_at,
                  INTERVAL %s HOUR
              )
              AND o.ordered_at < %s
            ORDER BY
                o.order_id,
                me.event_at,
                cc.campaign_cart_id
            """,
            (window_hours, SNAPSHOT_AT),
        )

        rows = cursor.fetchall()

        if not rows:
            print(
                "No eligible click-to-purchase matches found."
            )
            return

        # ------------------------------------------
        # STEP B: GROUP MATCHES BY ORDER
        # ------------------------------------------

        candidates_by_order = defaultdict(dict)

        for row in rows:

            (
                order_id,
                cart_id,
                ordered_at,
                order_total,
                campaign_cart_id,
                campaign_id,
                send_id,
                click_at,
            ) = row

            # Retain only the latest eligible click for
            # each order/campaign-cart combination.
            previous = candidates_by_order[
                order_id
            ].get(campaign_cart_id)

            candidate = {
                "order_id": order_id,
                "cart_id": cart_id,
                "ordered_at": ordered_at,
                "order_total": Decimal(str(order_total)),
                "campaign_cart_id": campaign_cart_id,
                "campaign_id": campaign_id,
                "send_id": send_id,
                "click_at": click_at,
            }

            if (
                previous is None
                or click_at > previous["click_at"]
            ):
                candidates_by_order[
                    order_id
                ][campaign_cart_id] = candidate

        # ------------------------------------------
        # STEP C: LOAD EXISTING LAST_CLICK RECORDS
        # ------------------------------------------

        cursor.execute(
            """
            SELECT DISTINCT order_id
            FROM attributions
            WHERE attribution_model = %s
            """,
            (ATTRIBUTION_MODEL,),
        )

        existing_order_ids = {
            row[0] for row in cursor.fetchall()
        }

        # This makes the script safe to rerun without
        # duplicating existing LAST_CLICK records.
        new_orders = {
            order_id: candidates
            for order_id, candidates
            in candidates_by_order.items()
            if order_id not in existing_order_ids
        }

        if not new_orders:
            print(
                "All eligible orders already have "
                "LAST_CLICK attribution records."
            )
            return

        # ------------------------------------------
        # STEP D: CHOOSE THE WINNING CLICK
        # ------------------------------------------

        attribution_records = []

        credited_orders = 0
        rejected_candidates = 0

        for order_id, candidate_map in new_orders.items():

            candidates = list(candidate_map.values())

            # Latest click wins. The campaign-cart ID
            # provides a deterministic tie-breaker.
            candidates.sort(
                key=lambda candidate: (
                    candidate["click_at"],
                    candidate["campaign_cart_id"],
                )
            )

            winner = candidates[-1]

            for candidate in candidates:

                is_winner = (
                    candidate["campaign_cart_id"]
                    == winner["campaign_cart_id"]
                )

                if is_winner:
                    status = "CREDITED"

                    credited_revenue = (
                        candidate["order_total"]
                    )

                else:
                    status = "REJECTED"

                    # Rejected candidates receive no
                    # credited revenue.
                    credited_revenue = Decimal("0.00")

                    rejected_candidates += 1

                attribution_records.append(
                    (
                        order_id,
                        candidate["campaign_cart_id"],
                        ATTRIBUTION_MODEL,
                        candidate["click_at"],
                        window_hours,
                        credited_revenue,
                        status,
                    )
                )

            credited_orders += 1

        # ------------------------------------------
        # STEP E: INSERT ATTRIBUTION RECORDS
        # ------------------------------------------

        cursor.executemany(
            """
            INSERT INTO attributions
            (
                order_id,
                campaign_cart_id,
                attribution_model,
                attributed_at,
                attribution_window_hours,
                credited_revenue,
                attribution_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            attribution_records,
        )

        connection.commit()

        # ------------------------------------------
        # STEP F: DISPLAY RESULTS
        # ------------------------------------------

        print("\n" + "=" * 50)
        print("ATTRIBUTION GENERATION COMPLETED")
        print("=" * 50)

        print(f"Attribution model: {ATTRIBUTION_MODEL}")
        print(f"Attribution window: {window_hours} hours")

        print(
            f"Eligible orders processed: "
            f"{credited_orders:,}"
        )

        print(
            f"Attribution records inserted: "
            f"{len(attribution_records):,}"
        )

        print(
            f"Orders receiving conversion credit: "
            f"{credited_orders:,}"
        )

        print(
            f"Rejected alternative candidates: "
            f"{rejected_candidates:,}"
        )

        print("\nAttribution status totals:")

        cursor.execute(
            """
            SELECT
                attribution_status,
                COUNT(*) AS total_records
            FROM attributions
            WHERE attribution_model = %s
            GROUP BY attribution_status
            ORDER BY attribution_status
            """,
            (ATTRIBUTION_MODEL,),
        )

        for status, total in cursor.fetchall():
            print(f"{status}: {total:,}")

        print("=" * 50)

    except (Error, ValueError, OSError, KeyError):
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 4. SCRIPT ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    try:
        generate_attributions()

    except (Error, ValueError, OSError, KeyError) as error:

        print(f"\nAttribution generation failed: {error}")

        raise SystemExit(1)