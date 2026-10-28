# src/generate_enrollments.py

import argparse
import bisect
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from db_connection import get_connection


SNAPSHOT_AT = datetime(2026, 10, 26, 0, 0, 0)
RANDOM_SEED = 20261022

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "project_config.json"


def load_config():
    """Load project configuration."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def fetch_all(cursor, query, params=None):
    """Execute a query and return its rows as dictionaries."""
    cursor.execute(query, params or ())
    return cursor.fetchall()


def latest_consent(consent_history, customer_id, channel, send_time):
    """
    Return the latest consent status effective at the proposed send time.

    Consent events are expected to contain:
    customer_id, channel, consent_status, effective_at, consent_event_id.
    """
    applicable_events = [
        event
        for event in consent_history.get((customer_id, channel), [])
        if event["effective_at"] <= send_time
    ]

    if not applicable_events:
        return None

    latest_event = max(
        applicable_events,
        key=lambda event: (
            event["effective_at"],
            event["consent_event_id"],
        ),
    )

    return latest_event["consent_status"]


def choose_pairs(campaigns, carts, target_sends, seed):
    """
    Choose unique campaign-cart pairs.

    A cart must have been abandoned while the campaign was active.
    Each pair can appear only once.
    """
    rng = random.Random(seed)

    valid_carts = [
        cart
        for cart in carts
        if cart["abandoned_at"] is not None
        and cart["abandoned_at"] <= SNAPSHOT_AT
    ]

    valid_carts.sort(key=lambda cart: cart["abandoned_at"])
    abandonment_times = [cart["abandoned_at"] for cart in valid_carts]

    shuffled_campaigns = list(campaigns)
    rng.shuffle(shuffled_campaigns)

    selected_pairs = []
    seen_pairs = set()

    for campaign in shuffled_campaigns:
        if len(selected_pairs) >= target_sends:
            break

        started_at = campaign["started_at"]
        ended_at = campaign["ended_at"]

        if started_at is None or ended_at is None:
            continue

        if ended_at < started_at:
            continue

        # Find carts abandoned during the campaign's active period.
        start_index = bisect.bisect_left(
            abandonment_times, started_at
        )
        end_index = bisect.bisect_right(
            abandonment_times, ended_at
        )

        if start_index >= end_index:
            continue

        # Try several random carts for this campaign.
        for _ in range(min(30, end_index - start_index)):
            cart_index = rng.randrange(start_index, end_index)
            cart = valid_carts[cart_index]

            pair_key = (campaign["campaign_id"], cart["cart_id"])

            if pair_key in seen_pairs:
                continue

            seen_pairs.add(pair_key)

            # Schedule the send at or after abandonment, while the
            # campaign is still within its configured time window.
            abandoned_at = cart["abandoned_at"]
            max_delay_seconds = max(
                0, int((ended_at - abandoned_at).total_seconds())
            )

            delay_seconds = rng.randint(
                0, min(max_delay_seconds, 24 * 60 * 60)
            )

            scheduled_at = abandoned_at + timedelta(
                seconds=delay_seconds
            )

            selected_pairs.append({
                "campaign": campaign,
                "cart": cart,
                "scheduled_at": scheduled_at,
            })

            break

    if len(selected_pairs) < target_sends:
        raise RuntimeError(
            f"Only {len(selected_pairs):,} unique eligible campaign-cart "
            f"pairs were found, but {target_sends:,} are required. "
            "No enrollment records have been inserted. Check campaign "
            "dates and cart abandonment timestamps."
        )

    return selected_pairs[:target_sends]


def main():
    parser = argparse.ArgumentParser(
        description="Generate campaign enrollments and send attempts."
    )
    parser.add_argument(
        "--mode",
        choices=["starter", "full"],
        default="starter",
        help="Dataset mode: starter or full.",
    )
    args = parser.parse_args()

    config = load_config()
    seed = config["project"].get("random_seed", RANDOM_SEED)

    target_sends = config["data_generation"][args.mode][
        "target_send_attempts"
    ]

    frequency_config = config["business_rules"]["frequency_cap"]
    max_messages = frequency_config["max_messages"]
    window_days = frequency_config["window_days"]

    rng = random.Random(seed)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Prevent duplicate enrollment/send generation.
        cursor.execute("SELECT COUNT(*) AS total FROM campaign_carts")
        enrollment_count = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM send_attempts")
        send_count = cursor.fetchone()["total"]

        if enrollment_count or send_count:
            raise RuntimeError(
                "campaign_carts or send_attempts already contains data. "
                "To avoid duplicate records, this script has stopped "
                "without inserting anything. Inspect the existing data "
                "before deciding how to proceed."
            )

        print(f"Loading data for mode: {args.mode}")
        print(f"Target send attempts: {target_sends:,}")

        # Load campaigns with usable active windows.
        campaigns = fetch_all(
            cursor,
            """
            SELECT campaign_id, channel, started_at, ended_at
            FROM campaigns
            WHERE started_at IS NOT NULL
              AND ended_at IS NOT NULL
              AND started_at <= ended_at
            """
        )

        # Load abandoned carts.
        carts = fetch_all(
            cursor,
            """
            SELECT cart_id, customer_id, abandoned_at
            FROM carts
            WHERE cart_status = 'ABANDONED'
              AND abandoned_at IS NOT NULL
              AND abandoned_at <= %s
            """,
            (SNAPSHOT_AT,),
        )

        # Load customer contact information.
        customers = fetch_all(
            cursor,
            """
            SELECT customer_id, email, phone
            FROM customers
            """
        )

        customer_lookup = {
            customer["customer_id"]: customer
            for customer in customers
        }

        # Load consent events.
        consent_events = fetch_all(
            cursor,
            """
            SELECT
                customer_id,
                channel,
                consent_status,
                effective_at,
                consent_event_id
            FROM consent_events
            ORDER BY effective_at, consent_event_id
            """
        )

        consent_history = defaultdict(list)

        for event in consent_events:
            key = (event["customer_id"], event["channel"])
            consent_history[key].append(event)

        # Select unique campaign-cart pairs.
        pairs = choose_pairs(
            campaigns=campaigns,
            carts=carts,
            target_sends=target_sends,
            seed=seed,
        )

        # Process sends in chronological order so the frequency cap
        # accounts for earlier accepted sends.
        pairs.sort(key=lambda pair: pair["scheduled_at"])

        accepted_send_times = defaultdict(list)
        enrollment_rows = []
        send_rows = []
        event_rows = []

        for index, pair in enumerate(pairs, start=1):
            campaign = pair["campaign"]
            cart = pair["cart"]
            scheduled_at = pair["scheduled_at"]

            campaign_id = campaign["campaign_id"]
            cart_id = cart["cart_id"]
            customer_id = cart["customer_id"]
            channel = campaign["channel"]

            customer = customer_lookup.get(customer_id)

            # Select the recipient from the customer's contact fields.
            recipient = ""
            if customer:
                if channel == "EMAIL":
                    recipient = (customer.get("email") or "").strip()
                elif channel == "SMS":
                    recipient = (customer.get("phone") or "").strip()

            suppression_reason = None

            if not recipient:
                suppression_reason = "MISSING_RECIPIENT"

            # Check consent at the actual scheduled send time.
            consent_status = latest_consent(
                consent_history,
                customer_id,
                channel,
                scheduled_at,
            )

            if suppression_reason is None and consent_status != "OPTED_IN":
                suppression_reason = "NO_VALID_OPT_IN"

            # Enforce the customer/channel rolling frequency cap.
            frequency_key = (customer_id, channel)
            cutoff = scheduled_at - timedelta(days=window_days)

            recent_sends = [
                send_time
                for send_time in accepted_send_times[frequency_key]
                if cutoff < send_time <= scheduled_at
            ]

            if (
                suppression_reason is None
                and len(recent_sends) >= max_messages
            ):
                suppression_reason = "FREQUENCY_CAP"

            if suppression_reason is None:
                accepted_send_times[frequency_key].append(scheduled_at)
                enrollment_status = "ELIGIBLE"
                send_status = "SENT"
            else:
                enrollment_status = "SUPPRESSED"
                send_status = "SUPPRESSED"

            send_id = f"SEND-2026-{index:06d}"

            # No message template is selected here; the actual schema
            # permits selected_template_id to be NULL.
            enrollment_rows.append({
                "campaign_id": campaign_id,
                "cart_id": cart_id,
                "selected_template_id": None,
                "enrolled_at": scheduled_at,
                "eligibility_status": enrollment_status,
                "suppression_reason": suppression_reason,
                "send_id": send_id,
                "customer_id": customer_id,
                "channel": channel,
                "recipient": recipient,
                "attempted_at": scheduled_at,
                "send_status": send_status,
            })

        # All writes are in one transaction. Any error triggers rollback.
        connection.commit()
        connection.start_transaction()

        for row in enrollment_rows:
            cursor.execute(
                """
                INSERT INTO campaign_carts (
                    campaign_id,
                    cart_id,
                    selected_template_id,
                    enrolled_at,
                    eligibility_status,
                    suppression_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    row["campaign_id"],
                    row["cart_id"],
                    row["selected_template_id"],
                    row["enrolled_at"],
                    row["eligibility_status"],
                    row["suppression_reason"],
                ),
            )

            # Use the generated bridge ID to link the send attempt.
            campaign_cart_id = cursor.lastrowid
            message_id = f"MSG-{campaign_cart_id:08d}"

            cursor.execute(
                """
                UPDATE campaign_carts
                SET message_id = %s
                WHERE campaign_cart_id = %s
                """,
                (message_id, campaign_cart_id),
        )

            cursor.execute(
                """
                INSERT INTO send_attempts (
                    send_id,
                    campaign_cart_id,
                    customer_id,
                    channel,
                    recipient,
                    attempted_at,
                    send_status,
                    suppression_reason,
                    provider_message_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["send_id"],
                    campaign_cart_id,
                    row["customer_id"],
                    row["channel"],
                    row["recipient"],
                    row["attempted_at"],
                    row["send_status"],
                    row["suppression_reason"],
                    None,
                ),
            )

            if row["send_status"] == "SENT":
                event_rows.extend([
                    (
                        row["send_id"],
                        "QUEUED",
                        row["attempted_at"],
                        None,
                        json.dumps({"source": "synthetic_generator"}),
                    ),
                    (
                        row["send_id"],
                        "SENT",
                        row["attempted_at"],
                        None,
                        json.dumps({"source": "synthetic_generator"}),
                    ),
                ])
            else:
                event_rows.append((
                    row["send_id"],
                    "FAILED",
                    row["attempted_at"],
                    None,
                    json.dumps({
                        "source": "synthetic_generator",
                        "suppression_reason": row["suppression_reason"],
                    }),
                ))

        if event_rows:
            cursor.executemany(
                """
                INSERT INTO message_events (
                    send_id,
                    event_type,
                    event_at,
                    provider_event_id,
                    event_details
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                event_rows,
            )

        connection.commit()

        sent_count = sum(
            1 for row in enrollment_rows
            if row["send_status"] == "SENT"
        )
        suppressed_count = len(enrollment_rows) - sent_count

        print("\nEnrollment generation completed successfully.")
        print(f"Mode: {args.mode}")
        print(f"Random seed: {seed}")
        print(f"Campaign-cart enrollments: {len(enrollment_rows):,}")
        print(f"Send attempts: {len(enrollment_rows):,}")
        print(f"Sent: {sent_count:,}")
        print(f"Suppressed: {suppressed_count:,}")
        print(f"Message events inserted: {len(event_rows):,}")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()